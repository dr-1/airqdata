#!/usr/bin/env python3

"""Access resources on luftdaten.info."""

import os
import warnings

import requests
import pandas as pd
from pandas.io.json import json_normalize
from matplotlib import pyplot as plt

from utils import (BaseSensor, cache_dir, retrieve, haversine,
                   label_coordinates)

# API
API_DOCUMENTATION_URL = "https://github.com/opendata-stuttgart/meta/wiki/APIs"
API_BASE_URL = "https://api.luftdaten.info/v1/"
API_ENDPOINTS = {"sensor metadata pattern":
                 API_BASE_URL + "sensor/{sensor_id}/",
                 "proximity search pattern":
                 API_BASE_URL + "filter/area={lat},{lon},{radius}"}

# Data archive
ARCHIVE_BASE_URL = "https://archive.luftdaten.info/"
ARCHIVE_URL_PATTERN = ARCHIVE_BASE_URL + "{date}/{filename}"
ARCHIVE_FILENAME_PATTERN = "{date}_{sensor_type}_sensor_{sensor_id}.csv"

# Other resources
WEBSITE_URL = "https://luftdaten.info"
MAP_URL = "https://maps.luftdaten.info"

UNITS = {"pm2.5": "µg/m³",
         "pm10": "µg/m³",
         "humidity": "%rh",
         "temperature": "°C"}


class Sensor(BaseSensor):
    """A sensor registered on luftdaten.info.

    Properties in addition to those of BaseSensor:
        metadata_url: URL on luftdaten.info that provides the sensor's
            metadata and current measurements.
    """

    def __init__(self, sensor_id, **retrieval_kwargs):
        """Establish sensor properties.

        Args:
            sensor_id: luftdaten.info sensor id
            retrieval_kwargs: keyword arguments to pass to retrieve
                function
        """
        super().__init__(sensor_id=sensor_id, affiliation="luftdaten.info")
        self.metadata_url = (API_ENDPOINTS["sensor metadata pattern"]
                             .format(sensor_id=sensor_id))
        self.get_metadata(**retrieval_kwargs)

    def get_metadata(self, **retrieval_kwargs):
        """Get sensor metadata and current measurements from cache or
        luftdaten.info API.

        Args:
            retrieval_kwargs: keyword arguments to pass to retrieve
                function

        Warns:
            UserWarning if sensor does not appear to be online
        """

        # Get and cache metadata and measurements of past five minutes
        filename = os.path.basename(self.metadata_url.rstrip("/")) + ".json"
        filepath = os.path.join(cache_dir, filename)
        parsed = retrieve(filepath, self.metadata_url,
                          "sensor {} metadata from luftdaten.info"
                          .format(self.sensor_id), **retrieval_kwargs)

        try:
            metadata = (parsed
                        .drop(columns=["sensordatavalues", "timestamp"])
                        .iloc[0])
        except ValueError:
            warnings.warn("Sensor metadata could not be retrieved")
        else:
            metadata.name = "metadata"
            self.metadata = metadata

            # Extract metadata into corresponding properties
            self.sensor_type = metadata["sensor.sensor_type.name"]
            self.lat = float(metadata["location.latitude"])
            self.lon = float(metadata["location.longitude"])
            self.label = "at " + label_coordinates(self.lat, self.lon)

            # Extract most current measurements
            current = parsed["sensordatavalues"].iloc[-1]
            current = (json_normalize(current)
                       .replace({"P1": "pm10", "P2": "pm2.5"})
                       .set_index("value_type")["value"])
            current = (pd.to_numeric(current)
                       .replace([999.9, 1999.9], pd.np.nan))
            self.current_measurements = dict(current)
            self.phenomena = list(current.index)
            self.units = {phenomenon: UNITS[phenomenon]
                          for phenomenon in UNITS
                          if phenomenon in self.phenomena}

    def get_measurements(self, start_date, end_date, **retrieval_kwargs):
        """Get measurement data of the sensor in a given period.

        Data are read from cache if available, or downloaded from
        luftdaten.info and saved to cache as retrieved, and then
        cleaned for self.measurements. If the instance already has data
        associated with it, calling this method replaces them.

        Args:
            start_date: first date of data to retrieve, in ISO 8601
                (YYYY-MM-DD) format
            end_date: last date of data to retrieve, in ISO 8601
                (YYYY-MM-DD) format
            retrieval_kwargs: keyword arguments to pass to retrieve
                function
        """
        sid = self.sensor_id
        if self.sensor_type is None:
            self.sensor_type = input("Type of sensor {} has not been set yet. "
                                     "Enter sensor type: ".format(sid))
        stype = self.sensor_type.lower()

        # Get and process the data file for each date in the requested range
        daily_data = []
        for date in pd.date_range(start_date, end_date):
            date_iso = date.strftime("%Y-%m-%d")
            filename = ARCHIVE_FILENAME_PATTERN.format(date=date_iso,
                                                       sensor_type=stype,
                                                       sensor_id=sid)
            filepath = os.path.join(cache_dir, filename)
            url = ARCHIVE_URL_PATTERN.format(date=date_iso, filename=filename)
            data = retrieve(filepath, url,
                            "luftdaten.info data for sensor {} on {}"
                            .format(sid, date_iso),
                            read_func=pd.read_csv,
                            read_func_kwargs={"sep": ";"}, **retrieval_kwargs)
            if data is None:
                continue

            # Parse timestamps and make them timezone aware
            timestamps = pd.to_datetime(data["timestamp"], utc=True)

            # Reformat data according to sensor type
            data.set_index(timestamps, inplace=True)
            if self.sensor_type in ("SDS011", "HPM"):
                data = (data[["P1", "P2"]]
                        .rename(columns={"P1": "pm10", "P2": "pm2.5"}))
            elif self.sensor_type == "DHT22":
                data = data[["temperature", "humidity"]]
            else:
                raise NotImplementedError("No data parsing method implemented "
                                          "for sensor type {}"
                                          .format(self.sensor_type))

            daily_data.append(data)

        # If daily data were retrieved, concatenate them to a single dataframe
        if daily_data:
            self.measurements = pd.concat(daily_data)
        else:
            self.measurements = None
            print("No data for sensor", sid)
            return

        # Remove duplicates
        duplicates = self.measurements.index.duplicated(keep="last")
        self.measurements = self.measurements[~duplicates]

        self.measurements.sort_index(inplace=True)
        self.clean_measurements()

    def clean_measurements(self):
        """Remove invalid measurements.

        Having several consecutive values under 1 µg/m³ indicates a
        problem with the sensor -> discard those values.

        Values of 999.9 µg/m³ (PM2.5) and 1999.9 µg/m³ (PM10) also
        indicate a problem.
        """

        # Remove values indicating errors
        self.measurements.replace([999.9, 1999.9], pd.np.nan, inplace=True)

        # Identify middle items in sequences of at least 5 dead measurements
        dead_5_middle = self.measurements.rolling(5, center=True).max() < 1.0

        # Expand to mask all items in such sequences
        dead_5_consecutive = dead_5_middle.rolling(5, center=True).max() == 1

        # Remove invalid values
        self.measurements[dead_5_consecutive] = pd.np.nan


def search_proximity(lat=50.848, lon=4.351, radius=8):
    """Find sensors within given radius from a location.

    Args:
        lat: latitude of the center of search, in decimal degrees
        lon: longitude of the center of search, in decimal degrees
        radius: maximum distance from center, in kilometers

    Default values are the approximate center and radius of Brussels.

    Returns:
        Dataframe of matching sensors, listing sensor types, locations
        and distances in kilometers from the search center, indexed by
        sensor ID
    """
    url = (API_ENDPOINTS["proximity search pattern"]
           .format(lat=lat, lon=lon, radius=radius))
    _json = requests.get(url).json()
    sensors = json_normalize(_json)
    if len(sensors) == 0:
        sensors = pd.DataFrame(columns=["sensor_type", "latitude", "longitude",
                                        "distance"])
        sensors.index.name = "sensor_id"
        return sensors
    sensors = (sensors[["sensor.id", "sensor.sensor_type.name",
                        "location.latitude", "location.longitude"]]
               .rename(columns={"sensor.id": "sensor_id",
                                "sensor.sensor_type.name": "sensor_type",
                                "location.latitude": "latitude",
                                "location.longitude": "longitude"}))
    for col in "latitude", "longitude":
        sensors[col] = pd.to_numeric(sensors[col], downcast="float")
    sensors.set_index("sensor_id", inplace=True)

    # Drop duplicates - sensors appear once for each measurement in past 5 mins
    sensors = sensors[~sensors.index.duplicated()]

    # Calculate distances from search center and sort by those distances
    sensors["distance"] = sensors.apply(lambda x:
                                        haversine(lat, lon,
                                                  float(x["latitude"]),
                                                  float(x["longitude"])),
                                        axis=1)
    sensors.sort_values("distance", inplace=True)

    return sensors


def evaluate_near_sensors(start_date, end_date, lat=50.848, lon=4.351,
                          radius=8, sensor_type="SDS011", show=True,
                          **retrieval_kwargs):
    """Create Sensor instances for all sensors of sensor_type near a
    location and get their measurement data.

    Coordinates and radius default to Brussels.

    Args:
        start_date: see Sensor.get_data
        end_date: see Sensor.get_data
        lat: see search_proximity
        lon: see search_proximity
        radius: see search_proximity
        sensor_type: sensor type label, e.g. "SDS011" or "DHT22"
        show: call plt.show; set to False to modify plots
        retrieval_kwargs: keyword arguments to pass to retrieve function

    Returns:
        sensors: list of Sensor instances, sorted by sensor IDs
        hourly_means: pandas dataframe of hourly measurement means of
            all sensors
    """
    near_sensors = search_proximity(lat=lat, lon=lon, radius=radius)

    # Filter by sensor type
    near_sensors = near_sensors[near_sensors["sensor_type"] == sensor_type]

    # Create list of Sensor instances
    sensors = [Sensor(sensor_id, **retrieval_kwargs)
               for sensor_id in near_sensors.index]

    sensors.sort(key=lambda sensor: sensor.sensor_id)
    hourly_means_pieces = []
    column_keys = []
    for sensor in sensors:
        sensor.get_measurements(start_date, end_date, **retrieval_kwargs)
        try:
            sensor_hourly_means = sensor.get_hourly_means()
        except AttributeError:
            continue
        else:
            hourly_means_pieces.append(sensor_hourly_means)
            column_keys.append(sensor.sensor_id)
    hourly_means = pd.concat(hourly_means_pieces, axis=1, keys=column_keys)
    hourly_means = hourly_means.swaplevel(0, 1, axis=1)
    hourly_means.sort_index(axis=1, level=0, inplace=True)
    for measure in ("pm10", "pm2.5"):
        (hourly_means.loc[:, measure]
         .plot(figsize=(16, 9), title=measure.upper()))
        plt.ylim(ymin=0)
        plt.ylabel("Concentration in µg/m³")
        if show:
            plt.show()
    return sensors, hourly_means
