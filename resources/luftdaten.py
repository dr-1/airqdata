#!/usr/bin/env python3

"""Access resources on luftdaten.info."""

import os

import requests
import pandas as pd
from pandas.io.json import json_normalize
import matplotlib as mpl
from matplotlib import pyplot as plt

from helpers import CACHE_DIR, retrieve, haversine

# API URLs
ARCHIVE_FILENAME_PATTERN = "{date}_{sensor_type}_sensor_{sensor_id}.csv"
ARCHIVE_URL_PATTERN = "https://archive.luftdaten.info/{date}/{filename}"
PROX_SEARCH_URL_PATTERN = ("https://api.luftdaten.info/v1/filter/"
                           "area={lat},{lon},{radius}")
SENSOR_URL_PATTERN = "https://api.luftdaten.info/v1/sensor/{sensor_id}/"


class Sensor:
    """A sensor registered on luftdaten.info."""

    def __init__(self, sensor_id, **retrieval_kwargs):
        """Establish sensor properties.

        Args:
            sensor_id: luftdaten.info sensor id
            retrieval_kwargs: keyword arguments to pass to retrieve
                function

        Properties:
            sensor_id: luftdaten.info sensor ID
            url: URL on luftdaten.info that provides the sensor's
                metadata and current measurements.
            metadata: pandas dataframe of sensor metadata from
                luftdaten.info
            sensor_type: sensor model, e.g. "SDS011" (particulate
                matter) or "DHT22" (temperature and relative humidity)
            current_values: dictionary of current measurements
            measurements: pandas dataframe of particulate matter
                measurements, empty at initialization
            hourly_means: hourly means of measurements where minimum
                data coverage is met
            hourly_coverage: ratio of available to ideal number of data
                points
            figs: placeholder for plots of measurements
            figs_hourly: placeholder for plots of hourly means
        """
        self.sensor_id = sensor_id
        self.url = SENSOR_URL_PATTERN.format(sensor_id=sensor_id)
        self.metadata = None
        self.sensor_type = None
        self.current_values = None
        self.measurements = None
        self.hourly_coverage = None
        self.hourly_means = None
        self.figs = {}
        self.figs_hourly = {}
        self.update(**retrieval_kwargs)

    def __repr__(self):
        """Instance representation."""
        memory_address = hex(id(self))
        return ("<luftdaten.info sensor {} at {}>"
                .format(self.sensor_id, memory_address))

    def update(self, **retrieval_kwargs):
        """Update sensor metadata and current measurements from cache or
        luftdaten.info API.

        Args:
            retrieval_kwargs: keyword arguments to pass to retrieve
                function

        Raises:
            ValueError if sensor does not appear to be online
        """

        # Get and cache metadata and measurements of past five minutes
        filename = os.path.basename(self.url.rstrip("/")) + ".json"
        filepath = os.path.join(CACHE_DIR, filename)
        parsed = retrieve(filepath, self.url,
                          "sensor {} metadata from luftdaten.info"
                          .format(self.sensor_id), **retrieval_kwargs)

        # Split metadata from measurements; keep only latest measurements.
        try:
            metadata = (parsed
                        .drop(columns=["sensordatavalues", "timestamp"])
                        .iloc[0])
        except ValueError:
            raise ValueError("Sensor does not appear to be online")
        metadata.name = "metadata"
        self.metadata = metadata
        self.sensor_type = metadata["sensor.sensor_type.name"]
        current = parsed["sensordatavalues"].iloc[-1]
        current = (json_normalize(current)
                   .replace({"P1": "pm10", "P2": "pm2.5"})
                   .set_index("value_type")["value"])
        current = (pd.to_numeric(current)
                   .replace([999.9, 1999.9], pd.np.nan))
        self.current_values = dict(current)

    def get_data(self, start_date, end_date, **retrieval_kwargs):
        """Get measurement data of the sensor in a given period.

        Data are read from cache if available, or downloaded from
        luftdaten.info and saved to cache as retrieved, and then
        cleaned for self.measurements. If the instance already has data
        associated with it, calling this method replaces them.

        Args:
            start_date: first date of data to retrieve, in
                ISO 8601 format, e.g. "2017-07-01"
            end_date: first date of data to retrieve, same format as
                start_date
            retrieval_kwargs: keyword arguments to pass to retrieve
                function
        """
        sid = self.sensor_id
        stype = self.sensor_type.lower()

        # Get and process the data file for each date in the requested range
        daily_data = []
        for date in pd.date_range(start_date, end_date):
            date_iso = date.strftime("%Y-%m-%d")
            filename = ARCHIVE_FILENAME_PATTERN.format(date=date_iso,
                                                       sensor_type=stype,
                                                       sensor_id=sid)
            filepath = os.path.join(CACHE_DIR, filename)
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
            if self.sensor_type == "SDS011":
                data = data[["P1", "P2"]]
                data.rename(columns={"P1": "pm10", "P2": "pm2.5"},
                            inplace=True)
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
            self.hourly_coverage = None
            self.hourly_means = None
            print("No data for sensor", self.sensor_id)
            return

        # Remove duplicates
        duplicates = self.measurements.index.duplicated(keep="last")
        self.measurements = self.measurements[~duplicates]

        self.measurements.sort_index(inplace=True)
        self.clean_data()
        self.calculate_hourly_coverage()
        self.calculate_hourly_means()

    def clean_data(self):
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

    @property
    def intervals(self):
        """Histogram of measurement intervals in seconds.

        Returns:
            Histogram of measurement intervals as a series, index-sorted
        """
        diffs = self.measurements.index.to_series().diff()
        diffs_seconds = diffs.dt.seconds
        return diffs_seconds.value_counts().sort_index()

    def calculate_hourly_coverage(self):
        """Calculate hourly ratio of available to ideal number of data
        points.
        """
        data_resampler = self.measurements.resample("h", kind="period")
        data_point_count = data_resampler.count()
        data_point_count.index.name = "Period"
        self.hourly_coverage = (data_point_count
                                .applymap(lambda x: min(1, x / 24)))

    def calculate_hourly_means(self, min_data_coverage=0.9):
        """Calculate hourly means of the data where data coverage is
        sufficient.

        Args:
            min_data_coverage: minimum ratio of available to ideal
                number of data points required calculate means. A
                coverage rate of 1.0 corresponds to 24 or 25
                measurements per hour as recorded by luftdaten.info.
        """
        if self.hourly_coverage is None:
            self.calculate_hourly_coverage()
        sufficient_coverage = self.hourly_coverage > min_data_coverage
        resampler = self.measurements.resample("h", kind="period")
        good_means = resampler.mean()[sufficient_coverage]
        good_means.index.name = "Period"
        self.hourly_means = good_means

    def plot_measurements(self):
        """Plot data as time series.

        Returns:
            Matplotlib AxesSubplot
        """
        for measure in self.measurements:
            self.figs[measure], ax = plt.subplots()
            title = ("Sensor {} - {} Measurements"
                     .format(self.sensor_id, measure.upper()))
            (self.measurements[measure]
             .plot(y="value", ax=ax, figsize=(12, 8), title=title, rot=90))
            ax.set(xlabel="Timestamp",
                   ylabel="Concentration in µg/m³",
                   ylim=(0, None))
            # ax.xaxis.set_major_formatter(_date_formatter)
            # FIXME: Shows date as 1146-12-24
            plt.xticks(horizontalalignment="center")
        plt.show()
        return ax

    def plot_hourly_means(self):
        """Plot data as time series.

        Returns:
            Matplotlib AxesSubplot
        """
        # TODO: Clean up x label format
        for measure in self.hourly_means:
            self.figs_hourly[measure], ax = plt.subplots()
            title = ("Sensor {} - {} Hourly Means"
                     .format(self.sensor_id, measure.upper()))
            (self.hourly_means[measure]
             .plot(y="value", figsize=(12, 8), ax=ax, title=title, rot=90))
            ax.set(xlabel="Timestamp",
                   ylabel="Concentration in µg/m³",
                   ylim=(0, None))
            # ax.xaxis.set_major_formatter(_date_formatter)
            # FIXME: Shows date as 1146-12-24
            plt.xticks(horizontalalignment="center")
        plt.show()
        return ax


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
    url = PROX_SEARCH_URL_PATTERN.format(lat=lat, lon=lon, radius=radius)
    _json = requests.get(url).json()
    sensors = json_normalize(_json)
    sensors = sensors[["sensor.id", "sensor.sensor_type.name",
                       "location.latitude", "location.longitude"]]
    sensors.rename(columns={"sensor.id": "sensor_id",
                            "sensor.sensor_type.name": "sensor_type",
                            "location.latitude": "latitude",
                            "location.longitude": "longitude"},
                   inplace=True)
    for col in "latitude", "longitude":
        sensors[col] = pd.to_numeric(sensors[col], downcast="float")
    sensors.set_index("sensor_id", inplace=True)

    # Drop duplicates - sensors appear once for each measurement in past 5 mins
    sensors = sensors[~sensors.index.duplicated()]

    # Calculate distances from search center and sort by those distances
    sensors["distance"] = sensors.apply(lambda x:
                                        haversine(lon, lat,
                                                  float(x["longitude"]),
                                                  float(x["latitude"])),
                                        axis=1)
    sensors.sort_values("distance", inplace=True)

    return sensors


def evaluate_near_sensors(start_date, end_date, lat=50.848, lon=4.351,
                          radius=8, **retrieval_kwargs):
    """Create Sensor instances for all sensors near a location and get
    their data.

    Coordinates and radius default to Brussels.

    Args:
        start_date: see Sensor.get_data
        end_date: see Sensor.get_data
        lat: see search_proximity
        lon: see search_proximity
        radius: see search_proximity
        retrieval_kwargs: keyword arguments to pass to retrieve function

    Returns:
        sensors: list of Sensor instances, sorted by sensor IDs
        hourly_means: pandas dataframe of hourly measurement means of
            all sensors
    """
    near_sensors = search_proximity(lat=lat, lon=lon, radius=radius)

    # Select PM sensors, disregard temperature/humidity sensors
    near_sds011 = near_sensors[near_sensors["sensor_type"] == "SDS011"]
    sensors = [Sensor(sensor_id, **retrieval_kwargs)
               for sensor_id in near_sds011.index]

    sensors.sort(key=lambda sensor: sensor.sensor_id)
    for sensor in sensors:
        sensor.get_data(start_date, end_date, **retrieval_kwargs)
    hourly_means = pd.concat([sensor.hourly_means for sensor in sensors],
                             axis=1,
                             keys=[sensor.sensor_id for sensor in sensors])
    hourly_means = hourly_means.swaplevel(0, 1, axis=1)
    hourly_means.sort_index(axis=1, level=0, inplace=True)
    for measure in ("pm10", "pm2.5"):
        (hourly_means.loc[:, measure]
         .plot(figsize=(16, 9), title=measure.upper()))
        plt.ylim(ymin=0)
        plt.ylabel("Concentration in µg/m³")
        plt.show()
    return sensors, hourly_means


# Output settings
_date_formatter = mpl.dates.DateFormatter("%Y-%m-%d\n%H:%M %Z")
plt.style.use("ggplot")
pd.set_option("display.precision", 2)
