package provision

import (
	"context"
	"encoding/json"
	"fmt"
	"hash/fnv"
	"os"
	"scaling_manager/cluster"
	log "scaling_manager/logger"
	"strings"

	opensearch "github.com/opensearch-project/opensearch-go"
	opensearchapi "github.com/opensearch-project/opensearch-go/opensearchapi"
)

// A global variable which stores the document ID of the State document that will to stored and fetched frm Opensearch
var docId = fmt.Sprint(hash(cluster.GetClusterId()))


// Input: string
//
// Description: Returns a hashed value of the string passed as input
//
// Output: uint32 (Hashed value of string)

func hash(s string) uint32 {
	h := fnv.New32a()
	h.Write([]byte(s))
	return h.Sum32()
}

// Index name where the State document will be stored
const IndexName = "monitor-stats-1"

// Global variable for Opensearch client to avoid multiple client creations
var client *opensearch.Client


// Input:
// Description: 
//	1. Initializes the opensearch client
//	2. Reads the mapping for the index to be created
//	3. Calls the createNewIndex function to create the index if not already present with defined mappings
// Output:
func init() {

	var err error
	client, err = opensearch.NewClient(opensearch.Config{
		Addresses: []string{"http://localhost:9200"},
	})
	if err != nil {
		log.Fatal(log.ProvisionerError, err)
		os.Exit(1)
	}

	mappingFile, err := os.ReadFile("provision/mappings.json") // just pass the file name
	if err != nil {
		log.Error(log.ProvisionerError, err)
	}
	mapping := string(mappingFile)

	createNewIndexWithMappings(mapping)
}

// Input: json string as mapping
// Description: 
//		Creates a new OS index if it doesn't exixts with the provided mapping
// Output:
func createNewIndexWithMappings(mapping string) {
	ctx := context.Background()
	createReq := opensearchapi.IndicesCreateRequest{}
	createReq.Index = IndexName
	createReq.Body = strings.NewReader(mapping)
	req := opensearchapi.IndicesExistsRequest{}
	req.Index = []string{IndexName}
	resp, err := req.Do(ctx, client)
	if err != nil {
		log.Fatal(log.ProvisionerError, fmt.Sprintf("Index exists check failed: %v", err))
	}
	log.Info(log.ProvisionerInfo, "Index already exists")
	if resp.Status() != "200 OK" {
		res, err := createReq.Do(ctx, client)
		if err != nil {
			log.Info(log.ProvisionerInfo, fmt.Sprintf("Create Index request error: %v ", err))
		}
		log.Info(fmt.Sprintf("Index create Response: %v", res))
	}
}

// Input:
// Description:
//
//      GetCurrentState will update the state variable pointer such that it is insync with the updated values.
//	Reads the document from Opensearch and updates the Struct
//
// Return:
//

func (s *State) GetCurrentState() {
	// Get the document.

	search := opensearchapi.GetRequest{
		Index:      IndexName,
		DocumentID: fmt.Sprint(docId),
	}

	searchResponse, err := search.Do(context.Background(), client)
	if err != nil {
		log.Fatal(log.ProvisionerError, fmt.Sprintf("failed to search document: %v ", err))
	}
	var stateInterface map[string]interface{}
	log.Info(log.ProvisionerInfo, fmt.Sprintf("Get resp: %v ", searchResponse))
	if searchResponse.Status() == "404 Not Found" {
		//Setting the initial state
		s.CurrentState = "normal"
		s.UpdateState()
		return
	}
	jsonErr := json.NewDecoder(searchResponse.Body).Decode(&stateInterface)
	if jsonErr != nil {
		log.Fatal(log.ProvisionerError, fmt.Sprintf("Unable to decode the response into interface: %v", jsonErr))
	}
	// convert map to json
	jsonString, errr := json.Marshal(stateInterface["_source"].(map[string]interface{}))
	if errr != nil {
		log.Fatal(log.ProvisionerFatal, fmt.Sprintf("Unable to unmarshal interface: %v", errr))
	}

	// convert json to struct
	json.Unmarshal(jsonString, s)
}

// Input:
//
// Description:
//
//      Updates the opensearch document with the values in state Struct pointer.
//
// Return:

func (s *State) UpdateState() {
	// Update the document.

	state, err := json.Marshal(s)
	if err != nil {
		log.Fatal(log.ProvisionerError, fmt.Sprintf("json.Marshal ERROR: %v", err))
	}
	content := string(state)

	updateReq := opensearchapi.IndexRequest{
		Index:      IndexName,
		DocumentID: fmt.Sprint(docId),
		Body:       strings.NewReader(content),
	}

	updateResponse, err := updateReq.Do(context.Background(), client)
	if err != nil {
		log.Fatal(log.ProvisionerError, fmt.Sprintf("failed to update document: %v ", err))
	}
	log.Info(log.ProvisionerInfo, fmt.Sprintf("Update resp: %v ", updateResponse))
}