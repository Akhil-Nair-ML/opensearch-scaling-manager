import time


class Cluster:
    """
    Acts as an interface for simulation of all associated nodes
    Performs and simulates the output of all operations performed
    by the master node.
    """

    def __init__(
            self,
            cluster_name: str,
            cluster_hostname: str,
            cluster_ip_address: str,
            node_machine_type_identifier: str,
            total_nodes_count: int,
            data_nodes_count: int,
            master_eligible_nodes_count: int,
            index_count: int,
            shards_per_index: int,
            index_roll_over_size: int,
            index_clean_up_age_days: int,

            status: str = "green",
            cpu_usage_percent: float = 0,
            memory_usage_percent: float = 0,
            disk_usage_percent: float = 0,
            heap_usage_percent: float = 0,
            total_shard_count: int = 0,
            initializing_shards_count: int = 0,
            relocating_shards_count: int = 0,
            unassigned_shards_count: int = 0,
            active_shards_count: int = 0,
            ingestion_rate: float = 0.0
    ):
        """
        Initialize the cluster object
        :param cluster_name: name of the cluster
        :param cluster_hostname: name of the cluster host
        :param cluster_ip_address: ip address of the cluster
        :param node_machine_type_identifier: type of machine on which elastic search is deployed
        :param total_nodes_count: total number of nodes of the cluster
        :param data_nodes_count: total number of data nodes of the cluster
        :param master_eligible_nodes_count: total number of master eligible nodes of the cluster
        :param index_count: total number of indexes in the cluster
        :param shards_per_index: maximum number of shards per index
        :param index_roll_over_size: size in bytes after which the index will be rolled over
        :param index_clean_up_age_days: time in minutes after which the index will be cleaned up
        :param status: status of the cluster from "green", "yellow" or "red"
        :param cpu_usage_percent: average cluster cpu usage in percent
        :param memory_usage_percent: average cluster memory usage in percent
        :param disk_usage_percent: average cluster disk usage in percent
        :param heap_usage_percent: average cluster heap memory usage in percent
        :param total_shard_count: total numer of shards present on the cluster
        :param initializing_shards_count: total number of shards in initializing state
        :param relocating_shards_count: total number of shards in relocating state
        :param unassigned_shards_count: total number of shards in unassigned state
        :param active_shards_count: total number of shards in active state
        """
        self.node_machine_type_identifier = node_machine_type_identifier
        self.name = cluster_name
        self.host_name = cluster_hostname
        self.ip_address = cluster_ip_address
        self.status = status
        self.cpu_usage_percent = cpu_usage_percent
        self.memory_usage_percent = memory_usage_percent
        self.disk_usage_percent = disk_usage_percent
        self.heap_usage_percent = heap_usage_percent
        self.total_nodes_count = total_nodes_count
        self.data_nodes_count = data_nodes_count
        self.master_eligible_nodes_count = master_eligible_nodes_count
        self.index_count = index_count
        self.index_roll_over_size = index_roll_over_size
        self.index_clean_up_age_in_minutes = index_clean_up_age_days
        self.total_shard_count = total_shard_count
        self.shards_per_index = shards_per_index
        self.initializing_shards = initializing_shards_count
        self.relocating_shards = relocating_shards_count
        self.unassigned_shards = unassigned_shards_count
        self.active_shards = active_shards_count
        self._ingestion_rate = ingestion_rate

    # TODO: Define methods for controlling cluster behaviour,
    #  node addition, removal etc
    # def add_node(self):
    #     pass
    #
    # def remove_node(self):
    #     pass
