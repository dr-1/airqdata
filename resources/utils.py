#!/usr/bin/env python3

"""Utility functions, constants and base classes."""

import sys
import os
import json
from io import BytesIO
from math import radians, cos, sin, asin, sqrt
from functools import partial

import requests
import pandas as pd
from pandas.io.json import json_normalize
import matplotlib as mpl
from matplotlib import pyplot as plt

CACHE_DIR = "./cache"

# Collection of equivalent phenomenon names for comparisons between
# sensors with different affiliations
EQUIVALENT_PHENOMENA = ({"pm2.5", "Particulate Matter < 2.5 µm"},
                        {"pm10", "Particulate Matter < 10 µm"},
                        {"temperature"})


class BaseSensor:
    """Generic sensor.

    Properties:
        sensor_id: unique identifier of the sensor
        label: sensor or location label
        affiliation: organization that the sensor belongs to
        metadata: pandas dataframe of sensor metadata
        lat: latitude of location
        lon: longitude of location
        alt: altitude of location
        sensor_type: name of the sensor type or model
        current_measurements: dict of current measurements
        measurements: pandas dataframe of measurements; timeseries
            indexed by datetime values; one column per phenomenon
        intervals: histogram of times between measurements
        phenomena: names of phenomena measured
        units: dict of measurement column names to units of measurement,
            e.g. {"pm2.5": "µg/m³"}
    """

    def __init__(self, sensor_id, affiliation=None):
        """Create a Sensor object.

        Args:
            sensor_id: unique identifier of the sensor
            affiliation: organization or collection of organizations
                that the sensor belongs to
        """
        self.sensor_id = sensor_id
        self.label = None
        self.affiliation = affiliation
        self.metadata = None
        self.lat = None
        self.lon = None
        self.alt = None
        self.sensor_type = None
        self.current_measurements = None
        self.measurements = None
        self.phenomena = None
        self.units = None

    def __repr__(self):
        """Instance representation."""
        memory_address = hex(id(self))
        if self.affiliation is not None:
            repr_string = ("<{} sensor {} at {}>"
                           .format(self.affiliation, self.sensor_id,
                                   memory_address))
        else:
            repr_string = ("<Sensor {} without affiliation at {}>"
                           .format(self.sensor_id, memory_address))
        return repr_string

    def get_metadata(self):
        """Get sensor metadata and current measurements if attached."""
        raise NotImplementedError("To be implemented in child classes")

    def get_measurements(self):
        """Get measurement data."""
        raise NotImplementedError("To be implemented in child classes")

    def clean_measurements(self):
        """Clean measurement data."""
        raise NotImplementedError("To be implemented in child classes")

    @property
    def intervals(self):
        """Histogram of times between measurements.

        Returns:
            Histogram of measurement intervals as a series, index-sorted
        """
        return self.measurements.index.to_series().diff().value_counts()

    def get_hourly_means(self, min_count=10):
        """Calculate hourly means from measurement data.

        Args:
            min_count: minimum number of data points per hour required
                to calculate means; periods failing this requirement
                will be pd.np.nan

        Returns:
            pandas dataframe of hourly means of measurements; timeseries
            indexed by hourly datetime values, with one column per
                phenomenon
        """
        resampler = self.measurements.resample("h", kind="period")
        hourly_means = resampler.sum(min_count=min_count) / resampler.count()
        hourly_means.index.name = "Period"
        return hourly_means

    def _plot_data(self, data, aggregation_level="Measurements", show=True):
        """Plot time series.

        Args:
            data: timeseries of one or more measures as a Pandas
                dataframe
            aggregation_level: aggregation level of the data, e.g.
                "Hourly Means", or "Measurements" for individual data
                points that are not aggregated
            show: call plt.show; set to False to modify plots

        Returns:
            List of Matplotlib figures
            List of Matplotlib axes

        Raises:
            KeyError if unit of measurement is not defined
        """
        figs, axes = [], []
        for phenomenon in data:
            try:
                unit = self.units[phenomenon]
            except KeyError:
                raise KeyError("Unit is not defined")
            fig, ax = plt.subplots()
            figs.append(fig)
            axes.append(ax)
            title = ("{affiliation} Sensor {sid} {label}\n{phenomenon} {level}"
                     .format(affiliation=self.affiliation or "Unaffiliated",
                             sid=self.sensor_id,
                             label=self.label or "Unlabeled",
                             phenomenon=phenomenon.upper(),
                             level=aggregation_level))
            data[phenomenon].plot(ax=ax, figsize=(12, 8), title=title, rot=90)
            ymin = min(0, data.min().min())  # Allows values below 0
            ax.set(xlabel="Timestamp",
                   ylabel="{} in {}".format(phenomenon, unit),
                   ylim=(ymin, None))
            plt.xticks(horizontalalignment="center")
        if show:
            plt.show()
        return figs, axes

    def plot_measurements(self, show=True):
        """Plot measurements as time series.

        Args:
            call plt.show; set to False to modify plots

        Returns:
            List of Matplotlib figures
            List of Matplotlib axes
        """
        return self._plot_data(self.measurements, show=show)

    def plot_hourly_means(self, *args, show=True, **kwargs):
        """Plot hourly means of measurements as time series.

        Args:
            args: positional arguments to pass to get_hourly_means
            kwargs: keyword arguments to pass to get_hourly_means
            show: call plt.show; set to False to modify plots

        Returns:
            List of Matplotlib figures
            List of Matplotlib axes
        """
        hourly_means = self.get_hourly_means(*args, **kwargs)
        return self._plot_data(hourly_means, show=show,
                               aggregation_level="Hourly Means")


def read_json(file, *_args, **_kwargs):
    """Read a semi-structured JSON file into a flattened dataframe.

    Args:
        file: file-like object
        _args: positional arguments receiver; not used
        _kwargs: keyword arguments receiver; not used

    Returns:
        Dataframe with single column level; original JSON hierarchy is
            expressed as dot notation in column names
    """
    if sys.version_info >= (3, 6):
        _json = json.load(file)
    else:  # In Python < 3.6, json.load does not accept bytes stream
        file_content_str = file.read().decode()
        _json = json.loads(file_content_str)
    flattened = json_normalize(_json)
    return flattened


def retrieve(cache_file, url, label, read_func=read_json, read_func_args=None,
             read_func_kwargs=None, refresh_cache=False, quiet=False):
    """Get a resource file from cache or from a URL and parse it.

    Cache downloaded data.

    Args:
        cache_file: path of the cached file. If it does not exist, the
            file is downloaded from the URL and saved to this path.
        url: URL to retrieve file from
        label: name of the information being retrieved, for printing to
            screen
        read_func: function to parse resource; must take a file object
            as its first argument and accept positional and keyword
            arguments
        read_func_args: sequence of positional arguments to pass to
            read_func
        read_func_kwargs: dict of keyword arguments to pass to read_func
        refresh_cache: boolean; when set to True, replace cached file
            with a new download
        quiet: do not show feedback

    Returns:
        Dataframe of content retrieved from cache_file or URL
    """
    if read_func_args is None:
        read_func_args = tuple()
    if read_func_kwargs is None:
        read_func_kwargs = {}
    if refresh_cache or not os.path.isfile(cache_file):

        # Download data
        quiet or print("Downloading", label)
        response = requests.get(url)

        # Handle HTTP error codes
        if response.status_code // 100 != 2:
            quiet or print("No {label}: status code {status_code}, "
                           "\"{reason}\""
                           .format(label=label,
                                   status_code=response.status_code,
                                   reason=response.reason))
            return

        # Cache downloaded data
        with open(cache_file, "wb") as file:
            file.write(response.content)

        # Load downloaded data into a buffer
        buffer = BytesIO(response.content)

    else:

        # Load cached file into a buffer
        quiet or print("Using cached", label)
        with open(cache_file, "rb") as file:
            buffer = BytesIO(file.read())

    return read_func(buffer, *read_func_args, **read_func_kwargs)


def haversine(lat1, lon1, lat2, lon2):
    """Calculate the great circle distance between two points on earth.

    Args:
        lat1, lon1, lat2, lon2: coordinates of point 1 and point 2 in
            decimal degrees

    Returns:
        Distance in kilometers
    """

    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = (radians(val) for val in (lat1, lon1, lat2, lon2))

    # Haversine formula
    d_lat = lat2 - lat1
    d_lon = lon2 - lon1
    a = sin(d_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(d_lon / 2) ** 2
    c = 2 * asin(sqrt(a))
    radius = 6371  # Radius of earth in kilometers
    distance = c * radius

    return distance


def label_coordinates(lat, lon):
    """Combine a set of numeric coordinates into a string with
    hemisphere indicators.

    Args:
        lat: latitude as float or int
        lon: longitude as float or int
    """
    ns_hemisphere = "N" if lat > 0 else "S"
    ew_hemisphere = "E" if lon > 0 else "W"
    label = "{}°{} {}°{}".format(lat, ns_hemisphere, lon, ew_hemisphere)
    return label


# Prepare caching
if not os.path.isdir(CACHE_DIR):
    os.makedirs(CACHE_DIR)

# Variant of pandas DataFrame.describe method showing an interval that contains
# 98% of the data, instead of the default interquartile range
describe = partial(pd.DataFrame.describe, percentiles=[0.01, 0.99])

# Plotting and table output settings
_date_formatter = mpl.dates.DateFormatter("%Y-%m-%d\n%H:%M %Z")
plt.style.use("ggplot")
pd.set_option("display.precision", 2)
