#!/usr/bin/env python3dd

"""Combine resources of Civic Labs Belgium, luftdaten.info, madavi.de
and irceline.be.
"""

import sys

import pandas as pd

# Allow dir-less imports in resource modules. This makes it possible to
# run those modules by themselves from their directory.
("resources" in sys.path) or sys.path.append("resources")

from resources import civiclabs
from resources import luftdaten
from resources import madavi
from resources import irceline
from resources.helpers import haversine, describe


def compare_sensor_and_station(sensor_id=None, sensor_obj=None,
                               start_date=None, end_date=None,
                               **retrieval_kwargs):
    """Compare the measurements of a Luftdaten sensor to the closest
    IRCELINE station(s). Values are plotted and returned.

    Args:

        Exactly one of sensor_id and sensor_obj must be given.
        Both start_date and end_date must be given.

        sensor_id: luftdaten.info sensor ID
        sensor_obj: luftdaten.Sensor instance
        start_date: date parameter to pass to luftdaten.Sensor.get_data
        end_date: date parameter to pass to luftdaten.Sensor.get_data
        retrieval_kwargs: keyword arguments to pass to retrieve function

    Returns:
        Dataframe of hourly means of sensor and station measurements
        List of measurement plots
    """

    # Check parameters
    if start_date is None or end_date is None:
        raise ValueError("Both start_date and end_date must be given")

    # Use or create luftdaten.Sensor instance and get sensor data
    if sensor_obj is not None:
        sensor = sensor_obj
    else:
        sensor = luftdaten.Sensor(sensor_id, **retrieval_kwargs)
    sensor.get_data(start_date=start_date, end_date=end_date,
                    **retrieval_kwargs)
    sensor.clean_data()

    # Find nearest stations and get their measurements
    nearest = find_nearest_pm_stations(sensor_obj=sensor,
                                       **retrieval_kwargs)
    measures = ("pm2.5", "pm10")
    data_nearest = {}
    for measure in measures:
        series_nearest = nearest.loc["time series id", measure]
        data_nearest[measure] = irceline.get_data(series_nearest,
                                                  start_date=start_date,
                                                  end_date=end_date,
                                                  **retrieval_kwargs)

    # Concatenate data
    station_data = pd.concat([data_nearest["pm2.5"], data_nearest["pm10"]],
                             axis=1, keys=["pm2.5", "pm10"])
    data = pd.concat([sensor.hourly_means, station_data], axis=1,
                     keys=["sensor", "station"])
    data = data.swaplevel(axis=1).sort_index(axis=1, level=0,
                                             ascending=False)

    # Create plots
    plots = []
    for measure in measures:
        station_label = nearest.loc["station_label", measure]
        distance = nearest.loc["distance", measure]
        title = ("{measure} Hourly Means\n"
                 "Sensor {sensor_id} Vs. Station \"{station_label}\"\n"
                 "Distance: {distance:.1f} km"
                 "".format(measure=measure.upper(),
                           sensor_id=sensor.sensor_id,
                           station_label=station_label,
                           distance=distance))
        plot = data[measure].plot(figsize=(16, 8), ylim=(0, None),
                                  title=title, legend=False)
        plot.legend(labels=[label.title()
                            for label in data[measure].columns])
        plot.set(ylim=(0, None),
                 xlabel="Time",
                 ylabel="Concentration in µg/m³")
        plots.append(plot)

    return data, plots


def find_nearest_pm_stations(sensor_id=None, sensor_obj=None,
                             **retrieval_kwargs):
    """Find the IRCELINE station(s) nearest to a given Luftdaten sensor
    that measure particulate matter. These may be the same or two
    different stations for the two types of PM measured.

    Args:

        Exactly one of sensor_id and sensor_obj must be given.

        sensor_id: luftdaten.info sensor ID
        sensor_obj: luftdaten.Sensor instance
        retrieval_kwargs: keyword arguments to pass to retrieve function

    Returns:
        Dataframe of nearest PM2.5 station and nearest PM10 station
    """

    # Check parameters
    if bool(sensor_id) + bool(sensor_obj) != 1:
        raise ValueError("Exactly one of sensor_id and sensor_obj must be "
                         "given")

    # Use or create luftdaten.Sensor instance
    if sensor_obj is not None:
        sensor = sensor_obj
    else:
        sensor = luftdaten.Sensor(sensor_id, **retrieval_kwargs)

    # Get sensor coordinates
    lat = float(sensor.metadata["location.latitude"])
    lon = float(sensor.metadata["location.longitude"])

    # Get IRCELINE metadata
    irceline_metadata = irceline.Metadata(**retrieval_kwargs)

    # Identify PM time series of nearest PM-measuring stations
    nearest = {}
    for (phen_short, phen_long) in (("pm10", "Particulate Matter < 10 µm"),
                                    ("pm2.5", "Particulate Matter < 2.5 µm")):
        matches = irceline_metadata.time_series["phenomenon"] == phen_long
        timeseries = irceline_metadata.time_series[matches].copy()
        timeseries["distance"] = timeseries.apply(lambda x:
                                                  haversine(lon, lat,
                                                            x["station_lon"],
                                                            x["station_lat"]),
                                                  axis=1)
        id_nearest = timeseries["distance"].argmin()
        timeseries["time series id"] = timeseries.index
        nearest[phen_short] = timeseries.loc[id_nearest]

    return pd.DataFrame(nearest)
