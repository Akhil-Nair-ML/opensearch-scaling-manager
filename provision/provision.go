// This package will fetch the recommendation from the recommendation Queue and provision the scale in/out
// based on command.
package provision

import (
	"bufio"
	"bytes"
	"context"
	"fmt"
	"net/http"
	"os"
	"scaling_manager/cluster"
	"scaling_manager/cluster_sim"
	"scaling_manager/config"
	utils "scaling_manager/utilities"
	"strings"
	"time"

	"scaling_manager/logger"

	"github.com/tkuchiki/faketime"
)

var log = new(logger.LOG)

// This struct contains the State of the opensearch scaling manager
// States can be of following types: (May change in real implementation with new stages identified)
// At any point, the state should have either "scaleup/scaledown" to identify the current operation happening
//
//   - normal : This is the state when the recommnedation will be provisioned.
//   - provisioning_scaleup/provisioning_scaledown : Once the provision module will start provisioning it will set this state.
//   - start_scaleup_process/start_scaledown_process : Indicates start of scaleup/scaledown process
//   - scaleup_triggered_spin_vm: Indicates trigger for spinning new vms while scaleup
//   - scaledown_node_identified: A state to identify node identification to scaledown
//   - provisioning_scaleup_completed/provisioning_scaledown_completed : Once the provision is completed then this state will be state.
//   - provisioning_scaleup_failed/provisioning_scaledown_failed: If the provision is failed then this state will be set.
//   - provisioned_scaleup_successfully/provisioned_scaledown_successfully: If the provision is completed and cluster state is green then this state will be set.
type State struct {
	// CurrentState indicate the current state of the scaling manager
	CurrentState string
	// PreviousState indicates the previous state of the scaling manager
	PreviousState string
	// Remark indicates the additional remarks for the state of the scaling manager
	Remark string
	// Last Provisioned time is when the last successful provision was completed
	LastProvisionedTime time.Time
	// Start time of the current provisioning in place
	ProvisionStartTime time.Time
	// Rule triggered for provisioning. i.e., scale_up/scale_down
	RuleTriggered string
	// Rule Responsible for provisioning. i.e., cpu, mem, heap, shard, disk.
	RulesResponsible string
	// Number of nodes being added(scale_up) / removed(scale_down) from the cluster due to current provision
	NumNodes int
	// Number of nodes remaining to be scaled up/scaled down
	RemainingNodes int
}

// Input:
//
// Description:
//
//	Initialize the Provision module.
//
// Return:
func init() {
	log.Init("logger")
	log.Info.Println("Provisioner module initiated")
}

// Input:
//
//	clusterCfg (config.ClusterDetails): Cluster Level config details
//	usrCfg (config.UserConfig): User defined config for applicatio behavior
//	numNodes (int): Number of nodes to be scaled up/down
//	operation (string): scaleup or scaledown operation
//	RulesResponsible (string): A string that contains the rules responsible for the decision of operation being performed
//	state (*State): A pointer to the state struct which is state maintained in OS document
//
// Description:
//
//	TriggerProvision will call scale in/out the cluster based on the operation.
//	ToDo:
//	        Think about the scenario where event based scaling needs to be performed.
//	        Morning need to scale up and evening need to scale down.
//	        If in morning the scale up was not successful then we should not perform the scale down.
//	        May be we can keep a concept of minimum number of nodes as a configuration input.
//
// Return:
func TriggerProvision(clusterCfg config.ClusterDetails, usrCfg config.UserConfig, state *State, numNodes int, t *time.Time, operation, RulesResponsible string) {
	state.GetCurrentState()
	if operation == "scale_up" {
		state.PreviousState = state.CurrentState
		state.CurrentState = "provisioning_scaleup"
		state.NumNodes = numNodes
		state.RemainingNodes = numNodes
		state.RuleTriggered = "scale_up"
		state.RulesResponsible = RulesResponsible
		state.UpdateState()
		isScaledUp := ScaleOut(clusterCfg, usrCfg, state, t)
		if isScaledUp {
			log.Info.Println("Scaleup successful")
		} else {
			state.GetCurrentState()
			// Add a retry mechanism
			state.PreviousState = state.CurrentState
			state.CurrentState = "provisioning_scaleup_failed"
			state.UpdateState()
			// Set the state back to normal to continue further
			setBackToNormal(state)
		}
	} else if operation == "scale_down" {
		state.PreviousState = state.CurrentState
		state.CurrentState = "provisioning_scaledown"
		state.NumNodes = numNodes
		state.RemainingNodes = numNodes
		state.RuleTriggered = "scale_down"
		state.RulesResponsible = RulesResponsible
		state.UpdateState()
		isScaledDown := ScaleIn(clusterCfg, usrCfg, state, t)
		if isScaledDown {
			log.Info.Println("Scaledown successful")
		} else {
			state.GetCurrentState()
			// Add a retry mechanism
			state.PreviousState = state.CurrentState
			state.CurrentState = "provisioning_scaledown_failed"
			state.UpdateState()
			// Set the state back to normal to continue further
			setBackToNormal(state)
		}
	}
}

// Input:
//
//	             clusterCfg (config.ClusterDetails): Cluster Level config details
//	             usrCfg (config.UserConfig): User defined config for applicatio behavior
//			state (*State): A pointer to the state struct which is state maintained in OS document
//
// Description:
//
//	ScaleOut will scale out the cluster with the number of nodes.
//	This function will invoke commands to create a VM based on cloud type.
//	Then it will configure the opensearch on newly created nodes.
//
// Return:
//
//	(bool): Return the status of scale out of the nodes.
func ScaleOut(clusterCfg config.ClusterDetails, usrCfg config.UserConfig, state *State, t *time.Time) bool {
	// Read the current state of scaleup process and proceed with next step
	// If no stage was already set. The function returns an empty string. Then, start the scaleup process
	state.GetCurrentState()
	var newNodeIp string
	simFlag := usrCfg.MonitorWithSimulator
	monitorWithLogs := usrCfg.MonitorWithLogs
	isAccelerated := usrCfg.isAccelerated

	switch state.CurrentState {
	case "provisioning_scaleup":
		log.Info.Println("Starting scaleUp process")
		time.Sleep(time.Duration(usrCfg.PollingInterval) * time.Second)
		if simFlag && isAccelerated {
			fakeSleep(t)
		}
		state.PreviousState = state.CurrentState
		state.CurrentState = "start_scaleup_process"
		state.ProvisionStartTime = time.Now()
		state.UpdateState()
		fallthrough
		// Spin new VMs based on number of nodes and cloud type
	case "start_scaleup_process":
		if monitorWithLogs {
			log.Info.Println("Spin new vms based on the cloud type")
			time.Sleep(time.Duration(usrCfg.PollingInterval) * time.Second)
			if simFlag && isAccelerated {
				fakeSleep(t)
			}
			log.Info.Println("Spinning AWS instance")
			time.Sleep(time.Duration(usrCfg.PollingInterval) * time.Second)
			if simFlag && isAccelerated {
				fakeSleep(t)
			}
		} else {
			var err error
			newNodeIp, err = SpinNewVm()
			if err != nil {
				state.LastProvisionedTime = time.Now()
				state.ProvisionStartTime = time.Time{}
				state.PreviousState = state.CurrentState
				state.CurrentState = "normal"
				state.UpdateState()
				return false
			}
		}
		log.Info.Println("Spinned a new node: ", newNodeIp)
		state.PreviousState = state.CurrentState
		state.CurrentState = "scaleup_triggered_spin_vm"
		state.UpdateState()
		fallthrough
	// Add the newly added VM to the list of VMs
	// Configure OS on newly created VM
	case "scaleup_triggered_spin_vm":
		if monitorWithLogs {
			log.Info.Println("Adding the spinned nodes into the list of vms")
			time.Sleep(time.Duration(usrCfg.PollingInterval) * time.Second)
			if simFlag && isAccelerated {
				fakeSleep(t)
			}
			log.Info.Println("Configure ES")
			time.Sleep(time.Duration(usrCfg.PollingInterval) * time.Second)
			if simFlag && isAccelerated {
				fakeSleep(t)
			}
			log.Info.Println("Configuring in progress")
			time.Sleep(time.Duration(usrCfg.PollingInterval) * time.Second)
			if simFlag && isAccelerated {
				fakeSleep(t)
			}
		} else {
			hostsFileName := "provision/ansible_scripts/hosts"
			username := "ubuntu"
			f, err := os.OpenFile(hostsFileName, os.O_RDWR|os.O_CREATE|os.O_TRUNC, 0644)
			if err != nil {
				log.Fatal.Println(err)
				state.LastProvisionedTime = time.Now()
				state.ProvisionStartTime = time.Time{}
				state.PreviousState = state.CurrentState
				state.CurrentState = "normal"
				state.UpdateState()
				return false
			}
			defer f.Close()
			nodes := utils.GetNodes()
			dataWriter := bufio.NewWriter(f)
			dataWriter.WriteString("[current-nodes]\n")
			for _, nodeIdMap := range nodes {
				_, _ = dataWriter.WriteString(nodeIdMap.(map[string]interface{})["name"].(string) + " " + "ansible_user=" + username + " roles=master,data,ingest ansible_private_host=" + nodeIdMap.(map[string]interface{})["hostIp"].(string) + " ansible_ssh_private_key_file=./testing-scaling-manager.pem\n")
			}
			dataWriter.WriteString("[new-node]\n")
			dataWriter.WriteString("new-node-" + fmt.Sprint(len(nodes)+1) + " ansible_user=" + username + " roles=master,data,ingest ansible_private_host=" + newNodeIp + " ansible_ssh_private_key_file=./testing-scaling-manager.pem\n")
			dataWriter.Flush()
			ansibleErr := CallScaleUp(username, hostsFileName)
			if ansibleErr != nil {
				log.Fatal.Println(err)
				state.LastProvisionedTime = time.Now()
				state.ProvisionStartTime = time.Time{}
				state.PreviousState = state.CurrentState
				state.CurrentState = "normal"
				state.UpdateState()
				return false
			}
		}
		state.PreviousState = state.CurrentState
		state.CurrentState = "provisioning_scaleup_completed"
		state.UpdateState()
		fallthrough
	// Check cluster status after the configuration
	case "provisioning_scaleup_completed":
		if simFlag {
			SimulateSharRebalancing("scaleOut", state.NumNodes)
		}
		log.Info.Println("Waiting for the cluster to become healthy")
		time.Sleep(time.Duration(usrCfg.PollingInterval) * time.Second)
		if simFlag && isAccelerated {
			fakeSleep(t)
		}
		CheckClusterHealth(state, usrCfg, t)
	}
	// Setting the state back to 'normal' irrespective of successful or failed provisioning to continue further
	setBackToNormal(state)
	return true
}

// Input:
//
//	clusterCfg (config.ClusterDetails): Cluster Level config details
//	usrCfg (config.UserConfig): User defined config for applicatio behavior
//	state (*State): A pointer to the state struct which is state maintained in OS document
//
// Description:
//
//	ScaleIn will scale in the cluster with the number of nodes.
//	This function will invoke commands to remove a node from opensearch cluster.
//
// Return:
//
//	(bool): Return the status of scale in of the nodes.
func ScaleIn(clusterCfg config.ClusterDetails, usrCfg config.UserConfig, state *State, t *time.Time) bool {
	// Read the current state of scaledown process and proceed with next step
	// If no stage was already set. The function returns an empty string. Then, start the scaledown process
	state.GetCurrentState()
	var removeNodeIp, removeNodeName string
	var nodes map[string]interface{}
	monitorWithLogs := usrCfg.MonitorWithLogs
	simFlag := usrCfg.MonitorWithSimulator
	isAccelerated := usrCfg.isAccelerated
	if state.CurrentState == "provisioning_scaledown" {
		log.Info.Println("Staring scaleDown process")
		state.PreviousState = state.CurrentState
		state.CurrentState = "start_scaledown_process"
		state.ProvisionStartTime = time.Now()
		state.UpdateState()
	}
	// Identify the node which can be removed from the cluster.
	switch state.CurrentState {
	case "start_scaledown_process":
		log.Info.Println("Identify the node to remove from the cluster and store the node_ip")
		if monitorWithLogs {
			time.Sleep(time.Duration(usrCfg.PollingInterval) * time.Second)
			if simFlag && isAccelerated {
				fakeSleep(t)
			}
		} else {
			nodes = utils.GetNodes()
			for nodeId, nodeIdInfo := range nodes {
				if !(utils.CheckIfMaster(context.Background(), nodeId)) {
					removeNodeIp = nodeIdInfo.(map[string]interface{})["hostIp"].(string)
					removeNodeName = nodeIdInfo.(map[string]interface{})["name"].(string)
					break
				}
			}
		}
		state.PreviousState = state.CurrentState
		state.CurrentState = "scaledown_node_identified"
		state.UpdateState()
		fallthrough
	// Configure OS to tell master node that the present node is going to be removed
	case "scaledown_node_identified":
		if monitorWithLogs {
			log.Info.Println("Configure ES to remove the node ip from cluster")
			time.Sleep(time.Duration(usrCfg.PollingInterval) * time.Second)
			if simFlag && isAccelerated {
				fakeSleep(t)
			}
			log.Info.Println("Shutdown the node by ssh")
			time.Sleep(time.Duration(usrCfg.PollingInterval) * time.Second)
			if simFlag && isAccelerated {
				fakeSleep(t)
			}
		} else {
			hostsFileName := "provision/ansible_scripts/hosts"
			username := "ubuntu"
			f, err := os.OpenFile(hostsFileName, os.O_RDWR|os.O_CREATE|os.O_TRUNC, 0644)
			if err != nil {
				log.Fatal.Println(err)
			}
			defer f.Close()
			dataWriter := bufio.NewWriter(f)
			dataWriter.WriteString("[current-nodes]\n")
			for _, nodeIdInfo := range nodes {
				if nodeIdInfo.(map[string]interface{})["hostIp"].(string) != removeNodeIp {
					_, _ = dataWriter.WriteString(nodeIdInfo.(map[string]interface{})["name"].(string) + " " + "ansible_user=" + username + " roles=master,data,ingest ansible_private_host=" + nodeIdInfo.(map[string]interface{})["hostIp"].(string) + " ansible_ssh_private_key_file=./testing-scaling-manager.pem\n")
				}
			}
			dataWriter.WriteString("[remove-node]\n")
			dataWriter.WriteString(removeNodeName + " " + "ansible_user=" + username + " roles=master,data,ingest ansible_private_host=" + removeNodeIp + " ansible_ssh_private_key_file=./testing-scaling-manager.pem\n")
			dataWriter.Flush()
			log.Info.Println("Removing node ***********************************:", removeNodeName)
			ansibleErr := CallScaleDown(username, hostsFileName)
			if ansibleErr != nil {
				log.Fatal.Println(err)
				state.LastProvisionedTime = time.Now()
				state.ProvisionStartTime = time.Time{}
				state.PreviousState = state.CurrentState
				state.CurrentState = "normal"
				state.UpdateState()
				return false
			}
		}
		state.PreviousState = state.CurrentState
		state.CurrentState = "provisioning_scaledown_completed"
		state.UpdateState()
		fallthrough
	// Wait for cluster to be in stable state(Shard rebalance)
	// Shut down the node
	case "provisioning_scaledown_completed":
		if simFlag {
			SimulateSharRebalancing("scaleIn", state.NumNodes)
		}
		log.Info.Println("Wait for the cluster to become healthy and then proceed")
		CheckClusterHealth(state, usrCfg, t)
		log.Info.Println("Shutdown the node")
		time.Sleep(time.Duration(usrCfg.PollingInterval) * time.Second)
		if simFlag && isAccelerated {
			fakeSleep(t)
		}
	}
	// Setting the state back to 'normal' irrespective of successful or failed provisioning to continue further
	setBackToNormal(state)
	return true
}

// Input:
//
//	state (*State): A pointer to the state struct which is state maintained in OS document
//	simFlag (bool): A flag to check if the task needs to collect stats from Opensearch data or simulated data.
//	pollingInterval (int): The time interval in seconds to wait until the next cluster health check happens
//
// Description:
//
//	CheckClusterHealth will check the current cluster health and also check if there are any relocating
//	shards. If the cluster status is green and there are no relocating shard then we will update the status
//	to provisioned_successfully. Else, we will wait for 3 minutes and perform this check again for 3 times.
//
// Return:
func CheckClusterHealth(state *State, usrCfg config.UserConfig, t *time.Time) {
	var clusterDynamic cluster.ClusterDynamic
	simFlag := usrCfg.MonitorWithSimulator
	pollingInterval := usrCfg.PollingInterval
	isAccelerated := usrCfg.IsAccelerated
	for i := 0; i <= 12; i++ {
		if simFlag {
			clusterDynamic = cluster_sim.GetClusterCurrent()
		} else {
			clusterDynamic = cluster.GetClusterCurrent()
		}
		log.Debug.Println(clusterDynamic.ClusterStatus)
		if clusterDynamic.ClusterStatus == "green" {
			state.GetCurrentState()
			state.PreviousState = state.CurrentState
			if strings.Contains(state.PreviousState, "scaleup") {
				state.CurrentState = "provisioned_scaleup_successfully"
			} else {
				state.CurrentState = "provisioned_scaledown_successfully"
			}
			state.UpdateState()
			break
		}
		log.Info.Println("Waiting for cluster to be healthy.......")
		time.Sleep(time.Duration(pollingInterval) * time.Second)
		if simFlag && isAccelerated {
			fakeSleep(t)
		}
	}
	state.GetCurrentState()
	if !(strings.Contains(state.CurrentState, "success")) {
		state.PreviousState = state.CurrentState
		if strings.Contains(state.PreviousState, "scaleup") {
			state.CurrentState = "provisioning_scaleup_failed"
		} else {
			state.CurrentState = "provisioning_scaledown_failed"
		}
		state.UpdateState()
		log.Warn.Println("Cluster hasn't come back to healthy state.")
	}
	// We should wait for buffer period after provisioned_successfully state to stablize the cluster.
	// After that buffer period we should change the state to normal, which can tell trigger module to trigger
	// the recommendation.
}

// Inputs:
//
//	operation (string): An input required by the simulator to know the operation being pperformed (scaleup/scaledown)
//	numNode (int): The number of nodes added/removed from the cluster to simulate
//
// Description:
//
//	Calls the simulator api with the details of nodes added/removed to simulate the shard rebalancing operation
//
// Return:
func SimulateSharRebalancing(operation string, numNode int) {
	// Add logic to call the simulator's end point
	byteStr := fmt.Sprintf("{\"nodes\":%d}", numNode)
	var jsonStr = []byte(byteStr)
	var urlLink string
	if operation == "scaleOut" {
		urlLink = fmt.Sprintf("http://localhost:5000/provision/addnode")
	} else {
		urlLink = fmt.Sprintf("http://localhost:5000/provision/remnode")
	}

	req, err := http.NewRequest("POST", urlLink, bytes.NewBuffer(jsonStr))
	req.Header.Set("Content-Type", "application/json")
	client := http.Client{
		Timeout: 10 * time.Second,
	}
	resp, err := client.Do(req)

	if err != nil {
		log.Panic.Println(err)
		panic(err)
	}

	if resp.StatusCode != 200 {
		log.Error.Println(resp.Status)
	}

	defer resp.Body.Close()
}

// Inputs:
//
//	t *time.Time
//
// Description:
//
//	Accelerate the sleep to the time duration mentioned in the input.
//
// Return:
func fakeSleep(t *time.Time) {
	*t = t.Add(time.Minute * 5)
	f := faketime.NewFaketimeWithTime(*t)
	f.Do()
	log.Info.Println(time.Now())
}

// Inputs:
//
//		state (*State): Pointer to the State struct
//
//	     Sets the CurrentState to normal, updates the other fields with default and updates the opensearch document with the same
//
// Return:
func setBackToNormal(state *State) {
	state.LastProvisionedTime = time.Now()
	state.ProvisionStartTime = time.Time{}
	state.PreviousState = state.CurrentState
	state.CurrentState = "normal"
	state.RuleTriggered = ""
	state.RemainingNodes = 0
	state.UpdateState()
	log.Info.Println("State set back to normal")
}
