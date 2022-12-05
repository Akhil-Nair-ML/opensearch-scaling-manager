import numpy as np
from scipy.interpolate import InterpolatedUnivariateSpline


class State:
    def __init__(
            self,
            position: int,
            time_hh_mm_ss: str,
            ingestion_rate_gb_per_hr: int
    ):
        self.position = position
        self.time_hh_mm_ss = time_hh_mm_ss
        self.ingestion_rate_gb_per_hr = ingestion_rate_gb_per_hr


class DataIngestion:
    def __init__(
            self,
            states: list[State],
            randomness_percentage: int
    ):
        self.states = states
        self.randomness_percentage = randomness_percentage

    def random_aggregation_points(
            self,
            duration_minutes: int,
            frequency_minutes: int
    ):
        print('aggregating random patterns')
        # positions to inter/extrapolate
        intervals = int(duration_minutes / frequency_minutes) + 1
        random_set = np.random.randint(0, self.randomness_percentage, size=intervals)
        x = np.linspace(0, duration_minutes, intervals)
        return x, random_set

    def data_aggregation_points(
            self,
            start_time_hh_mm_ss: str,
            duration_minutes: int,
            frequency_minutes: int):
        """
        Produce cumulative data points of all events and return an array of resultant aggregation
        :param start_time_hh_mm_ss: start time in hh_mm_ss in 24-hour format, eg. '080000'
        :param duration_minutes: duration of point generation in minutes
        :param frequency_minutes: gap between the resultant points
        :return: array of float containing resultant data aggregation points
        """

        # fits
        time_of_day = []
        ingestion_rate_gb_per_hour = []


        for state in self.states:
            time_of_day.append(state.time_hh_mm_ss)
            ingestion_rate_gb_per_hour.append(state.ingestion_rate_gb_per_hr)

        time_of_day = [int(i.split('_')[0]) * 60 for i in time_of_day]

        print('ingestion_rate_gb_per_hour', ingestion_rate_gb_per_hour)
        print('time_of_day', time_of_day)

        # add missing value of 0th hour
        if time_of_day[0] != 0:
            time_of_day.insert(0, 0)
            ingestion_rate_gb_per_hour.insert(0, 5)

        # positions to inter/extrapolate
        intervals = int(duration_minutes / frequency_minutes) + 1

        x = np.linspace(0, duration_minutes, intervals)
        # spline order: 1 linear, 2 quadratic, 3 cubic ...
        order = 1
        # do inter/extrapolation
        s = InterpolatedUnivariateSpline(time_of_day, ingestion_rate_gb_per_hour, k=order)
        y = s(x)
        return x, y

    def aggregate_data(
            self,
            start_time_hh_mm_ss: str,
            duration_minutes: int,
            frequency_minutes: int
    ):
        x, y1 = self.data_aggregation_points(start_time_hh_mm_ss, duration_minutes, frequency_minutes)
        x, y2 = self.random_aggregation_points(duration_minutes, frequency_minutes)
        return x, y1+y2
