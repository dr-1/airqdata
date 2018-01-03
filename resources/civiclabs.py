#!/usr/bin/env python3

"""Access Civic Labs Belgium resources."""

import pandas as pd

from utils import CACHE_DIR, retrieve

SENSOR_SHEET_URL = ("https://docs.google.com/spreadsheets/d/1J8WTKryYjZHfBQrMS"
                    "Yjwj6uLOBmWWLftaTqeicKVfYE/export?format=csv")
SENSOR_INFO_CACHE_FILE = CACHE_DIR + "/civic_labs_sensors.csv"


def get_sensors(**retrieval_kwargs):
    """Download sensor information from Civic Labs' Google Sheet and
    cache it.

    Args:
        retrieval_kwargs: keyword arguments to pass to retrieve function

    Returns:
        Dataframe of sensors with chip ID, sensor ID and address

    Raises:
        KeyError if sheet structure does not match listed columns
    """
    sensors = retrieve(SENSOR_INFO_CACHE_FILE, SENSOR_SHEET_URL,
                       "Civic Labs sensor information",
                       read_func=pd.read_csv,
                       read_func_kwargs={"header": 1, "dtype": "object"},
                       **retrieval_kwargs)
    try:
        sensors = sensors[["Chip ID", "PM Sensor ID", "Hum/Temp Sensor ID",
                           "Address"]]
    except KeyError:
        raise KeyError("Could not get columns. Check if the structure or "
                       "labels of the Civic Labs sensor Google Sheet have "
                       "changed.")
    return sensors


if __name__ == "__main__":
    sensors = get_sensors()
