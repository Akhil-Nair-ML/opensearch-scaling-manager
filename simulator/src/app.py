from flask import Flask, jsonify, request
import constants
from config_parser import parse_config
from simulator import Simulator
from cluster import Cluster
from data_ingestion import State, DataIngestion


app = Flask(__name__)


@app.route('/stats/avg/<string:stat_name>/<int:duration>')
def average(stat_name, duration):
    return jsonify(
        {
            "avg": sim.get_cluster_average(constants.STAT_REQUEST[stat_name], duration),
            "min": sim.get_cluster_min(constants.STAT_REQUEST[stat_name], duration),
            "max": sim.get_cluster_max(constants.STAT_REQUEST[stat_name], duration),
        }
    )


@app.route('/stats/current/<string:stat_name>')
def current(stat_name):
    return jsonify(
        {
            "current": sim.get_cluster_current(constants.STAT_REQUEST[stat_name])
        }
    )


@app.route('/stats/violated/<string:stat_name>/<int:duration>/<float:threshold>')
def violated_count(stat_name, duration, threshold):
    return jsonify(
        {
            "ViolatedCount": sim.get_cluster_violated_count(constants.STAT_REQUEST[stat_name], duration, threshold)
        }
    )


configs = parse_config('config.yaml')
all_states = [State(**state) for state in configs.data_ingestion.get('states')]
randomness_percentage = configs.data_ingestion.get('randomness_percentage')

data_function = DataIngestion(all_states, randomness_percentage)

cluster = Cluster(**configs.stats)

sim = Simulator(cluster, data_function, configs.searches, configs.data_generation_interval_minutes, 0)
# generate the data points from simulator
sim.run(24*60)
# start serving the apis
app.run(port=constants.APP_PORT)
