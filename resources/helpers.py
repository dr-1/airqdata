#!/usr/bin/env python3

"""Helper functions and constants."""

import os
import json
from io import BytesIO
from math import radians, cos, sin, asin, sqrt
from functools import partial

import requests
import pandas as pd
from pandas.io.json import json_normalize

CACHE_DIR = "./cache"


def read_json(file, *_args, **_kwargs):
    """Read a semi-structured JSON file into a flattened dataframe.

    Args:
        file: file object to read
        _args: positional arguments receiver; not used
        _kwargs: keyword arguments receiver; not used
    """
    _json = json.load(file)
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
                           "".format(label=label,
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
