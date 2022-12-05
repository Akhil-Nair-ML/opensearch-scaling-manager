import os
import copy
import pickle
import random
from datetime import datetime, timedelta

import constants
from cluster import Cluster
from data_ingestion import DataIngestion
from search import Search


class Simulator:
    """
    Takes care of:
        - creation of cluster
        - triggering of events
        - altering the states of nodes and cluster based on events
        - providing the current statistics of node and cluster
    """

    def __init__(
            self,
            cluster: Cluster,
            data_ingestion: DataIngestion,
            searches: list[Search],
            frequency_minutes: int,
            elapsed_time_minutes: int = 0,
    ):
        """
        Initialize the Simulator object
        :param elapsed_time_minutes: if provided, the cluster
            represents the state after the elapsed minutes
        """

        self.cluster = cluster
        self.data_ingestion = data_ingestion
        self.searches = searches
        self.elapsed_time_minutes = elapsed_time_minutes
        self.frequency_minutes = frequency_minutes

    def aggregate_data(
            self,
            duration_minutes,
            start_time_hh_mm_ss: str = '00_00_00'
    ):
        # first collect all data aggregation events
        x, y = self.data_ingestion.aggregate_data(start_time_hh_mm_ss, duration_minutes, self.frequency_minutes)
        return x, y

    def cpu_used_for_ingestion(self, ingestion):
        return min(ingestion / self.cluster.total_nodes_count * random.randrange(1, 15) / 100 * 100, 100)

    def memory_used_for_ingestion(self, ingestion):
        return min(ingestion / self.cluster.total_nodes_count * random.randrange(5, 12) / 100 * 100, 100)

    def cluster_state_for_ingestion(self, ingestion):
        if ingestion < constants.HIGH_INGESTION_RATE_GB_PER_HOUR:
            return random.choice([constants.CLUSTER_STATE_GREEN] * 10 + [constants.CLUSTER_STATE_YELLOW])
        if self.cluster.status == constants.CLUSTER_STATE_RED:
            return random.choice([constants.CLUSTER_STATE_YELLOW, constants.CLUSTER_STATE_RED])
        return random.choice(
            [constants.CLUSTER_STATE_GREEN] * 5 + [constants.CLUSTER_STATE_YELLOW] * 3 + [constants.CLUSTER_STATE_RED])

    def file_name_for_pickling(self, passed_minutes: int, passed_days: int = 0):
        now = datetime.now()
        date_obj = now - timedelta(
            hours=now.hour,
            minutes=now.minute,
            seconds=now.second,
            microseconds=now.microsecond
        )
        resultant_time = date_obj + timedelta(minutes=passed_minutes, days=passed_days)
        return resultant_time.strftime(constants.DATE_TIME_FORMAT)

    def run(self, duration_minutes):
        resultant_cluster_objects = []
        data_x, data_y = self.aggregate_data(duration_minutes)
        if not os.path.exists(constants.DATA_FOLDER):
            os.makedirs(constants.DATA_FOLDER)
        for y in data_y:
            self.cluster._ingestion_rate = y
            self.cluster.cpu_usage_percent = self.cpu_used_for_ingestion(y)
            self.cluster.memory_usage_percent = self.memory_used_for_ingestion(y)
            self.cluster.status = self.cluster_state_for_ingestion(y)
            self.elapsed_time_minutes += self.frequency_minutes
            # Todo: simulate effect on remaining cluster parameters 
            resultant_cluster_objects.append(copy.deepcopy(self.cluster))
            with open(os.path.join(constants.DATA_FOLDER, self.file_name_for_pickling(self.elapsed_time_minutes)),
                      'wb') as f:
                pickle.dump(self.cluster, f)

        return resultant_cluster_objects

    def get_cluster_average(self, stat_name, duration_minutes, elapsed_time: int = -1):
        cluster_objects = []
        data_points_file_names = []
        if elapsed_time == -1:
            now = datetime.now()
            date_obj = now - timedelta(
                minutes=now.minute % self.frequency_minutes,
                seconds=now.second,
                microseconds=now.microsecond
            )
            for duration in range(0, duration_minutes, self.frequency_minutes):

                data_points_file_names.append(
                    (date_obj - timedelta(minutes=duration)).strftime(constants.DATE_TIME_FORMAT))
        # Todo: implement logic when elapsed time is passed

        for file_name in reversed(data_points_file_names):
            with open(os.path.join(constants.DATA_FOLDER, file_name), 'rb') as f:
                cluster_objects.append(pickle.load(f))

        return sum([cluster.__getattribute__(stat_name) for cluster in cluster_objects]) / len(cluster_objects)

    def get_cluster_min(self, stat_name, duration_minutes, elapsed_time: int = -1):
        cluster_objects = []
        data_points_file_names = []
        if elapsed_time == -1:
            now = datetime.now()
            date_obj = now - timedelta(
                minutes=now.minute % self.frequency_minutes,
                seconds=now.second,
                microseconds=now.microsecond
            )
            for duration in range(0, duration_minutes, self.frequency_minutes):
                data_points_file_names.append(
                    (date_obj - timedelta(minutes=duration)).strftime(constants.DATE_TIME_FORMAT))
                print((date_obj - timedelta(minutes=duration)).strftime(constants.DATE_TIME_FORMAT))
        # Todo: implement logic when elapsed time is passed

        for file_name in reversed(data_points_file_names):
            with open(os.path.join(constants.DATA_FOLDER, file_name), 'rb') as f:
                cluster_objects.append(pickle.load(f))

        return min([cluster.__getattribute__(stat_name) for cluster in cluster_objects])

    def get_cluster_max(self, stat_name, duration_minutes, elapsed_time: int = -1):
        cluster_objects = []
        data_points_file_names = []
        if elapsed_time == -1:
            now = datetime.now()
            date_obj = now - timedelta(
                minutes=now.minute % self.frequency_minutes,
                seconds=now.second,
                microseconds=now.microsecond
            )
            for duration in range(0, duration_minutes, self.frequency_minutes):
                data_points_file_names.append(
                    (date_obj - timedelta(minutes=duration)).strftime(constants.DATE_TIME_FORMAT))
                print((date_obj - timedelta(minutes=duration)).strftime(constants.DATE_TIME_FORMAT))
        # Todo: implement logic when elapsed time is passed

        for file_name in reversed(data_points_file_names):
            with open(os.path.join(constants.DATA_FOLDER, file_name), 'rb') as f:
                cluster_objects.append(pickle.load(f))

        return max([cluster.__getattribute__(stat_name) for cluster in cluster_objects])

    def get_cluster_current(self, stat_name, elapsed_time_minutes=-1):
        if elapsed_time_minutes == -1:
            now = datetime.now()
            date_obj = now - timedelta(
                minutes=now.minute % self.frequency_minutes,
                seconds=now.second,
                microseconds=now.microsecond
            )
            file_name = date_obj.strftime(constants.DATE_TIME_FORMAT)
            with open(os.path.join(constants.DATA_FOLDER, file_name), 'rb') as f:
                cluster_object = pickle.load(f)
                return cluster_object.__getattribute__(stat_name)

    def get_cluster_violated_count(self, stat_name, duration_minutes, threshold, elapsed_time: int = -1):
        cluster_objects = []
        data_points_file_names = []
        if elapsed_time == -1:
            now = datetime.now()
            date_obj = now - timedelta(
                minutes=now.minute % self.frequency_minutes,
                seconds=now.second,
                microseconds=now.microsecond
            )
            for duration in range(0, duration_minutes, self.frequency_minutes):
                data_points_file_names.append(
                    (date_obj - timedelta(minutes=duration)).strftime(constants.DATE_TIME_FORMAT))
                print((date_obj - timedelta(minutes=duration)).strftime(constants.DATE_TIME_FORMAT))
        # Todo: implement logic when elapsed time is passed

        for file_name in reversed(data_points_file_names):
            with open(os.path.join(constants.DATA_FOLDER, file_name), 'rb') as f:
                cluster_objects.append(pickle.load(f))
        violatioed_count = 0
        for cluster in cluster_objects:
            if cluster.__getattribute__(stat_name) > threshold:
                violatioed_count += 1
        return violatioed_count
