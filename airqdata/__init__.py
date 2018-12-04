#!/usr/bin/env python3

"""Combine resources of the InfluencAir project, luftdaten.info,
madavi.de and irceline.be.
"""

import pandas as pd
from matplotlib import pyplot as plt

from airqdata import influencair, irceline, luftdaten, madavi
from airqdata.utils import (EQUIVALENT_PHENOMENA, describe, cache_dir,
                            clear_cache)

__version__ = "0.2"


def compare_sensor_data(sensors, phenomena, start_date, end_date,
                        hourly_means=True, show_plots=True,
                        **retrieval_kwargs):
    """Compare the measurements of a group of sensors.

    Values are plotted and returned.

    Args:
        sensors: sequence of sensor objects, instances of
            utils.BaseSensor
        phenomena: sequence of column names of the data to use; order
            corresponding to sensors parameter
        start_date: start date of measurements to compare, in ISO 8601
            (YYYY-MM-DD) format
        end_date: end date of measurements to compare, in ISO 8601
            (YYYY-MM-DD) format
        hourly_means: boolean; compare hourly means of measurements
            instead of measurements themselves
        show_plots: call show on returned plots; set to False to modify
            plots before displaying them
        retrieval_kwargs: keyword arguments to pass to retrieve function

    Returns:
        Combined dataframe of sensors' measurements or their hourly
            means
        Matplotlib AxesSubplot of the combined data
    """
    data_pieces = []
    combined_columns = []
    ylabels = []
    for sensor, column in zip(sensors, phenomena):

        # Retrieve and collect data
        sensor.get_measurements(start_date=start_date, end_date=end_date,
                                **retrieval_kwargs)
        sensor.clean_measurements()
        if hourly_means:
            data = sensor.get_hourly_means()
        else:
            data = sensor.measurements
        data = data[column]
        data_pieces.append(data)

        # Build and collect column names for combined dataframe
        key = (column, str(sensor.sensor_id) + " " + sensor.label,
               sensor.affiliation)
        combined_columns.append(key)

        # Build and collect y axis labels
        ylabel = "{} in {}".format(column, sensor.units[column])
        ylabels.append(ylabel)

    # Combine data from sensors into single dataframe
    combined_data = pd.concat(data_pieces, axis=1, keys=combined_columns)
    combined_data.columns.names = ["Phenomenon", "Sensor", "Affiliation"]

    # Plot data
    aggregation_level = "Hourly Means" if hourly_means else "Measurements"
    title = "Comparison of Sensor {}".format(aggregation_level)
    ymin = min(0, combined_data.min().min())  # Allows values below 0
    plot = combined_data.plot(title=title, ylim=(ymin, None), figsize=(16, 8))
    plot.axes.set_ylabel("\n".join(label for label in ylabels))
    if show_plots:
        plt.show()

    return combined_data, plot


def compare_nearest_irceline_sensors(sensor, start_date, end_date,
                                     **retrieval_kwargs):
    """Compare a sensor's measurements (hourly means) to those of the
    closest IRCELINE sensor(s) that measure equivalent phenomena.

    Args:
        sensor: sensor object, instance of utils.BaseSensor
        start_date: start date of measurements to compare, in ISO 8601
            (YYYY-MM-DD) format
        end_date: end date of measurements to compare, in ISO 8601
            (YYYY-MM-DD) format
        retrieval_kwargs: keyword arguments to pass to retrieve function

    Returns:
        Combined dataframe of the hourly means of the sensors'
            measurements
        List of Matplotlib AxesSubplots of the combined data, one for
            each phenomenon
    """
    nearest_irceline_sensors = (irceline
                                .find_nearest_sensors(sensor,
                                                      **retrieval_kwargs))
    combined_data_pieces = []
    plots = []
    for phenomenon in nearest_irceline_sensors:
        irceline_time_series_id = nearest_irceline_sensors.at["time series id",
                                                              phenomenon]
        irceline_phenomenon = nearest_irceline_sensors.at["phenomenon",
                                                          phenomenon]
        distance = nearest_irceline_sensors.at["distance", phenomenon]
        irceline_sensor = irceline.Sensor(irceline_time_series_id)
        irceline_station_label = nearest_irceline_sensors.at["station_label",
                                                             phenomenon]
        (combined_data_piece,
         plot) = compare_sensor_data([sensor, irceline_sensor],
                                     [phenomenon, irceline_phenomenon],
                                     start_date, end_date, show_plots=False,
                                     **retrieval_kwargs)
        title = (plot.axes.get_title()
                 + ("\n{phenomenon} at {affiliation} {sid} {label}\n"
                    "{irceline_phenomenon} at IRCELINE {irceline_tsid} "
                    "{irceline_station_label}\n"
                    "Distance: {distance:.1f} km"
                    .format(phenomenon=phenomenon,
                            affiliation=sensor.affiliation,
                            sid=sensor.sensor_id,
                            label=sensor.label,
                            irceline_phenomenon=irceline_phenomenon,
                            irceline_tsid=irceline_time_series_id,
                            irceline_station_label=irceline_station_label,
                            distance=distance)))
        plot.axes.set_title(title)
        combined_data_pieces.append(combined_data_piece)
        plots.append(plot)
    combined_data = pd.concat(combined_data_pieces, axis=1)
    plt.show()

    return combined_data, plots
