# This is the main module of OpenSearch Cluster simulator
# The intent of this module is to simulate the behaviour of a cluster
# under varies loading conditions

import sys

import constants
from config_parser import parse_config
from simulator import Simulator
from cluster import Cluster
from data_ingestion import State, DataIngestion
from plotter import plot_graphs_with_same_x


if __name__ == '__main__':
    # print(sys.argv)
    # input('...')
    configs = parse_config('config.yaml')
    all_states = [State(**state) for state in configs.data_ingestion.get('states')]
    randomness_percentage = configs.data_ingestion.get('randomness_percentage')

    data_function = DataIngestion(all_states, randomness_percentage)

    cluster = Cluster(**configs.stats)

    sim = Simulator(cluster, data_function, configs.searches, configs.data_generation_interval_minutes, 0)
    # generate the data points
    result = sim.run(24*60)
    # get y-coordinates to plot on graph
    y1 = [res._ingestion_rate for res in result]
    y2 = [res.cpu_usage_percent for res in result]
    y3 = [res.memory_usage_percent for res in result]

    def map_cluster_state(state: str):
        """
        Maps state of cluster -  green, yellow and red to 33.33, 66.66 and 100 respectively,
        so that they can be plotted on a graph
        :param state: state of the cluster - green, yellow or red
        :return: decimal representation of the state
        """
        if state == constants.CLUSTER_STATE_GREEN:
            return 33.33
        elif state == constants.CLUSTER_STATE_YELLOW:
            return 66.66
        return 100


    y4 = [map_cluster_state(res.status) for res in result]
    x = [x for x in range(0, 24 * 60 + 1, 5)]
    plot_graphs_with_same_x(x, [y1, y2, y3, y4])

    # print information from reading the data points
    print(sim.get_cluster_average(constants.STAT_REQUEST['cpu'], 60))
    print(sim.get_cluster_average(constants.STAT_REQUEST['memory'], 60))
