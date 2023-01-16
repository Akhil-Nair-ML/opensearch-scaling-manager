import os
import shutil
import json
from datetime import datetime, timedelta
from threading import Thread

from flask import Flask, jsonify, Response, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text, desc
from werkzeug.exceptions import BadRequest

import constants
from config_parser import parse_config, get_source_code_dir
from open_search_simulator import Simulator
from cluster_dynamic import ClusterDynamic
from plotter import plot_data_points


app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///datapoints.db"
app.app_context().push()
if os.path.exists("instance"):
    shutil.rmtree("instance")
db = SQLAlchemy(app)

# Database model to store the datapoints
class DataModel(db.Model):
    status = db.Column(db.String(200))
    cpu_usage_percent = db.Column(db.Float, default=0)
    memory_usage_percent = db.Column(db.Float, default=0)
    heap_usage_percent = db.Column(db.Float, default=0)
    shards_count = db.Column(db.Integer, default=0)
    total_nodes_count = db.Column(db.Integer, default=0)
    active_shards_count = db.Column(db.Integer, default=0)
    active_primary_shards = db.Column(db.Integer, default=0)
    initializing_shards_count = db.Column(db.Integer, default=0)
    unassigned_shards_count = db.Column(db.Integer, default=0)
    relocating_shards_count = db.Column(db.Integer, default=0)
    master_eligible_nodes_count = db.Column(db.Integer, default=0)
    active_data_nodes = db.Column(db.Integer, default=0)
    date_created = db.Column(db.DateTime, default=datetime.now(), primary_key=True)
    disk_usage_percent = db.Column(db.Integer, default = 0)

def get_provision_status():
   return is_provisioning

def set_provision_status(bool_val):
    global is_provisioning 
    is_provisioning = bool_val
 

def get_first_data_point_time():
    """
    Function queries the database for the time corresponding to first data point
    generated by the simulator
    :return: Time corresponding to first data point generated by the simulator
    """
    first_data_point_time = (
        DataModel.query.order_by(DataModel.date_created)
            .with_entities(DataModel.date_created)
            .first()
    )
    return first_data_point_time[0]


def cluster_db_object(cluster):
    """
    Create a DataModel instance that can be dumped into db
    :param cluster: cluster object
    :return: data model
    """
    return DataModel(
        cpu_usage_percent=cluster.cpu_usage_percent,
        memory_usage_percent=cluster.memory_usage_percent,
        heap_usage_percent=cluster.heap_usage_percent,
        date_created=cluster.date_time,
        status=cluster.status,
        total_nodes_count=cluster.total_nodes_count,
        active_shards_count=cluster.active_shards,
        active_primary_shards=cluster.active_primary_shards,
        initializing_shards_count=cluster.initializing_shards,
        unassigned_shards_count=cluster.unassigned_shards,
        relocating_shards_count=cluster.relocating_shards,
        master_eligible_nodes_count=cluster.master_eligible_nodes_count,
        active_data_nodes=cluster.active_data_nodes,
        disk_usage_percent = cluster_obj.disk_usage_percent
    )


def overwrite_after_node_count_change(cluster_objects):
    """
    Calculate the resource utilization after node change operation
    and overwrite the saved data points in db after node change time.
    Also create an overlap on the png file to show new data points
    :param cluster_objects: all cluster objects with new node configuration
    :param date_time: date time object to overwrite date time now
    :return: expiry time
    """
    date_time = datetime.now()
    cluster_objects_post_change = []
    for cluster_obj in cluster_objects:
        if cluster_obj.date_time >= date_time:
            cluster_objects_post_change.append(cluster_obj)
            task = cluster_db_object(cluster_obj)
            db.session.merge(task)
    db.session.commit()
    plot_data_points(cluster_objects_post_change, skip_data_ingestion=True, skip_search_query=True)
    # expiry_time = Simulator.create_provisioning_lock()
    return

def add_node_and_rebalance(nodes):
    """
    Increments node count in cluster object and rebalances the shards
    among the available nodes. Re-Simulates the data once the node is 
    added and shards are distributed
    """
    app.app_context().push()
    sim = Simulator(
            configs.cluster,
            configs.data_function,
            configs.search_description,
            configs.searches,
            configs.simulation_frequency_minutes
        )
    sim.cluster.add_nodes(nodes)
    cluster_objects = sim.run(24 * 60)
    # expiry_time = overwrite_after_node_count_change(cluster_objects)
    overwrite_after_node_count_change(cluster_objects)
    is_provisioning = get_provision_status()
    is_provisioning = False
    set_provision_status(is_provisioning) 

def rem_node_and_rebalance(nodes):
    """
    Decrements node count in cluster object and rebalances the shards
    among the available nodes. Re-Simulates the data once the node is 
    removed and shards are distributed
    """
    app.app_context().push()
    sim = Simulator(configs.cluster, 
                    configs.data_function, 
                    configs.search_description, 
                    configs.searches, 
                    configs.simulation_frequency_minutes)
    sim.cluster.remove_nodes(nodes)
    cluster_objects = sim.run(24 * 60)
    # expiry_time = overwrite_after_node_count_change(cluster_objects)
    overwrite_after_node_count_change(cluster_objects)
    is_provisioning = get_provision_status()
    is_provisioning = False
    set_provision_status(is_provisioning)


@app.route("/stats/violated/<string:stat_name>/<int:duration>/<float:threshold>")
def violated_count(stat_name, duration, threshold):
    """
    Endpoint fetches the violated count for a requested metric, threshold and duration,
    :param stat_name: represents the stat that is being queried.
    :param duration: represents the time period for fetching the average
    :param threshold: represents the limit considered for evaluating violated count
    :return: count of stat exceeding the threshold for a given duration
    """
    # calculate time to query for data
    time_now = datetime.now()

    # Convert the minutes to time object to compare and query for required data points
    query_begin_time = time_now - timedelta(minutes=duration)
    first_data_point_time = get_first_data_point_time()
    try:
        # Fetching the count of data points for given duration.
        data_point_count = (
            DataModel.query.order_by(constants.STAT_REQUEST[stat_name])
                .filter(DataModel.date_created > query_begin_time)
                .filter(DataModel.date_created < time_now)
                .count()
        )

        # If expected data points are not present then respond with error
        if first_data_point_time > query_begin_time:
            return Response(json.dumps("Not enough Data points"), status=400)

        # Fetches the count of stat_name that exceeds the threshold for given duration
        stats = (
            DataModel.query.order_by(constants.STAT_REQUEST[stat_name])
                .filter(
                DataModel.__getattribute__(DataModel, constants.STAT_REQUEST[stat_name])
                > threshold
            )
                .filter(DataModel.date_created > query_begin_time)
                .filter(DataModel.date_created < time_now)
                .count()
        )

        return jsonify({"ViolatedCount": stats})

    except KeyError:
        return Response(f"stat not found - {stat_name}", status=404)
    except Exception as e:
        return Response(e, status=404)


@app.route("/stats/avg/<string:stat_name>/<int:duration>")
def average(stat_name, duration):
    """
    The endpoint evaluates average of requested stat for a duration
    returns error if sufficient data points are not present.
    :param stat_name: represents the stat that is being queried.
    :param duration: represents the time period for fetching the average
    :return: average of the provided stat name for the decision period.
    """
    # calculate time to query for data
    time_now = datetime.now()
    # Convert the minutes to time object to compare and query for required data points
    query_begin_time = time_now - timedelta(minutes=duration)
    first_data_point_time = get_first_data_point_time()
    stat_list = []
    try:
        # Fetches list of rows that is filter by stat_name and are filtered by decision period
        avg_list = (
            DataModel.query.order_by(constants.STAT_REQUEST[stat_name])
                .filter(DataModel.date_created > query_begin_time)
                .filter(DataModel.date_created < time_now)
                .with_entities(text(constants.STAT_REQUEST[stat_name]))
                .all()
        )
        for avg_value in avg_list:
            stat_list.append(avg_value[0])

        # If expected data points count are not present then respond with error
        if first_data_point_time > query_begin_time:
            return Response(json.dumps("Not enough Data points"), status=400)

        # check if any data points were collected
        if not stat_list:
            return Response(json.dumps("Not enough Data points"), status=400)

        # Average, minimum and maximum value of a stat for a given decision period
        return jsonify(
            {
                "avg": sum(stat_list) / len(stat_list),
                "min": min(stat_list),
                "max": max(stat_list),
            }
        )

    except KeyError:
        return Response(f"stat not found - {stat_name}", status=404)
    except Exception as e:
        return Response(e, status=404)


@app.route("/stats/current/<string:stat_name>")
def current(stat_name):
    """
    The endpoint to fetch stat from the latest poll,
    Returns error if sufficient data points are not present.
    :return: Stat generated by the most recent poll
    """
    try:
        if constants.STAT_REQUEST[stat_name] == constants.CLUSTER_STATE:
            if Simulator.is_provision_in_progress():
                return jsonify({"current": constants.CLUSTER_STATE_YELLOW})
        # Fetches the stat_name for the latest poll
        current_stat = (
            DataModel.query.order_by(desc(DataModel.date_created))
                .with_entities(
                DataModel.__getattribute__(DataModel, constants.STAT_REQUEST[stat_name])
            )
                .all()
        )

        # If expected data points count are not present then respond with error
        if len(current_stat) == 0:
            return Response(json.dumps("Not enough Data points"), status=400)

        return jsonify({"current": current_stat[0][constants.STAT_REQUEST[stat_name]]})

    except KeyError:
        return Response(f"stat not found - {stat_name}", status=404)
    except Exception as e:
        return Response(e, status=404)


@app.route("/stats/current")
def current_all():
    """The endpoint returns all the stats from the latest poll,
    Returns error if sufficient data points are not present."""
    is_provisioning = get_provision_status()
    if is_provisioning:
        return jsonify(cluster_dynamic.__dict__)
    try:
        stat_dict = {}
        for key in constants.STAT_REQUEST_CURRENT:
            value = (
                DataModel.query.order_by(desc(DataModel.date_created))
                    .with_entities(
                    DataModel.__getattribute__(
                        DataModel, constants.STAT_REQUEST_CURRENT[key]
                    )
                )
                    .all()
            )
            stat_dict[key] = value[0][0]
        return jsonify(stat_dict)

    except Exception as e:
        return Response(str(e), status=404)


@app.route("/provision/addnode", methods=["POST"])
def add_node():
    """
    Endpoint to simulate that a node is being added to the cluster
    Expects request body to specify the number of nodes added
    :return: total number of resultant nodes and duration of cluster state as yellow
    """
    is_provisioning = get_provision_status()
    if is_provisioning:
        return Response(json.dumps("Cannot perform requested operation as Provisioning is in progress"),status=404)
    is_provisioning = True
    set_provision_status(is_provisioning)

    try:
        nodes = int(request.json['nodes'])
        node_count = sim.cluster.total_nodes_count + nodes
    except BadRequest as err:
        is_provisioning = False
        set_provision_status(is_provisioning)
        return Response(json.dumps("expected key 'nodes'"), status=404)
    add_node_thread = Thread(target = add_node_and_rebalance, args = (nodes, ))
    add_node_thread.start()
    return jsonify({
        'nodes': node_count
    })


@app.route("/provision/remnode", methods=["POST"])
def remove_node():
    """
    Endpoint to simulate that a node is being removed from the cluster
    Expects request body to specify the number of nodes added
    :return: total number of resultant nodes and duration of cluster state as yellow
    """
    is_provisioning = get_provision_status()
    if is_provisioning:
        return Response(json.dumps("Cannot perform requested operation as Provisioning is in progress"),status=404)
    is_provisioning = True
    set_provision_status(is_provisioning)

    try:
        nodes = int(request.json['nodes'])
        node_count = sim.cluster.total_nodes_count - nodes
        if sim.cluster.total_nodes_count - nodes < sim.cluster.min_nodes_in_cluster:
            return Response(json.dumps("Cannot remove more node(s), Minum nodes required: ", sim.cluster.min_nodes_in_cluster), status=404)
    except BadRequest as err:
        is_provisioning = False
        set_provision_status(is_provisioning)
        return Response(json.dumps("expected key 'nodes'"), status=404)
    rem_node_thread = Thread(target = rem_node_and_rebalance, args = (nodes, ))
    rem_node_thread.start()
    return jsonify({
        'nodes': node_count
    })

@app.route("/all")
def all_data():
    """
    Endpoint to fetch the count of datapoints generated by simulator
    :return: returns the count of total datapoints generated by the simulator
    """
    count = DataModel.query.with_entities(
        DataModel.cpu_usage_percent, DataModel.memory_usage_percent, DataModel.status
    ).count()
    return jsonify(count)


if __name__ == "__main__":
    db.create_all()
    cluster_dynamic = ClusterDynamic()
    # remove any existing provision lock
    is_provisioning = False
    Simulator.remove_provisioning_lock()
    # get configs from config yaml
    configs = parse_config(
        os.path.join(get_source_code_dir(), constants.CONFIG_FILE_PATH)
    )
    # create the simulator object
    sim = Simulator(
        configs.cluster,
        configs.data_function,
        configs.search_description,
        configs.searches,
        configs.simulation_frequency_minutes,
    )
    sim.cluster.cluster_dynamic = cluster_dynamic
    # generate the data points from simulator
    cluster_objects = sim.run(24 * 60)
    # save the generated data points to png
    plot_data_points(cluster_objects)
    # save data points inside db
    for cluster_obj in cluster_objects:
        task = cluster_db_object(cluster_obj)
        db.session.add(task)
    db.session.commit()

    # start serving the apis
    app.run(port=constants.APP_PORT)
