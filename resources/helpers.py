#!/usr/bin/env python3

"""Helper functions and constants."""

import os
import json
from io import BytesIO
from math import radians, cos, sin, asin, sqrt
from functools import partial

import requests
import pandas as pd
from pandas.io.json import json_normalize as json_normalize

CACHE_DIR = "./cache"


def retrieve(cache_file, url, label, refresh_cache=False, format="json",
             quiet=False, **read_csv_kwargs):
    """Get a resource file from cache or from a URL and parse it.

    Cache downloaded data.

    Args:
        cache_file: path of the cached file. If it does not exist, the
            file is downloaded from the URL and saved to this path.
        url: URL to retrieve file from
        label: name of the information being retrieved, for printing to
            screen
        refresh_cache: boolean; when set to True, replace cached file
            with a new download
        format: data format of the source. Can handle "json" and "csv".
        quiet: do not show feedback
        read_csv_kwargs: keyword arguments to pass to pd.read_csv. Only
            used if format is set to "csv".

    Returns:
        Dataframe of content retrieved from cache_file or URL

    Raises:
        ValueError if format parameter is not one of "json", "csv"
    """

    # Check input
    if format not in ("json", "csv"):
        raise ValueError("Format must be \"json\" or \"csv\"")

    # Check cache
    cached = os.path.isfile(cache_file)

    if refresh_cache or not cached:

        # Download data
        quiet or print("Downloading", label)
        response = requests.get(url)
        if response.status_code // 100 != 2:
            quiet or print("No {label}: status code {status_code}, "
                           "\"{reason}\""
                           "".format(label=label,
                                     status_code=response.status_code,
                                     reason=response.reason))
            return

        # Cache downloaded data
        with open(cache_file, "wb") as file:
            file.write(response.content)

        # Parse
        if format == "json":
            _json = response.json()
            return json_normalize(_json)  # Flattens nested JSON
        csv_buffer = BytesIO(response.content)
        return pd.read_csv(csv_buffer, **read_csv_kwargs)

    # Retrieve from cache
    quiet or print("Using cached", label)
    if format == "json":
        with open(cache_file, "r") as file:
            _json = json.load(file)
        return json_normalize(_json)
    return pd.read_csv(cache_file, **read_csv_kwargs)


def haversine(lon1, lat1, lon2, lat2):
    """Calculate the great circle distance between two points on earth.

    Args:
        lon1, lat1, lon2, lat2: coordinates of point 1 and point 2 in
            decimal degrees

    Returns:
        Distance in kilometers
    """

    # Convert decimal degrees to radians
    lon1, lat1, lon2, lat2 = (radians(val) for val in (lon1, lat1, lon2, lat2))

    # Haversine formula
    d_lon = lon2 - lon1
    d_lat = lat2 - lat1
    a = sin(d_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(d_lon / 2) ** 2
    c = 2 * asin(sqrt(a))
    radius = 6371  # Radius of earth in kilometers
    distance = c * radius

    return distance


# Prepare caching
if not os.path.isdir(CACHE_DIR):
    os.makedirs(CACHE_DIR)

# Variant of pandas DataFrame.describe method showing an interval that contains
# 98% of the data, instead of the default interquartile range
describe = partial(pd.DataFrame.describe, percentiles=[0.01, 0.99])
