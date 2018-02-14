#!/usr/bin/env python3

"""Access InfluencAir resources.

InfluencAir is a project created by Civic Lab Brussels.
"""

import pandas as pd

from utils import CACHE_DIR, retrieve

# Resources
SENSOR_SHEET_URL = ("https://docs.google.com/spreadsheets/d/1J8WTKryYjZHfBQrMS"
                    "Yjwj6uLOBmWWLftaTqeicKVfYE/export?format=csv")
WEBSITE_URLS = {"https://influencair.be",
                "https://www.meetup.com/Civic-Lab-Brussels"}
MAP_URL = "http://influencair.be/map-brussels/"

# Caching
SENSOR_INFO_CACHE_FILE = CACHE_DIR + "/civic_labs_sensors.csv"


def get_sensor_info(**retrieval_kwargs):
    """Retrieve sensor information from the InfluencAir project.

    Args:
        retrieval_kwargs: keyword arguments to pass to retrieve function

    Returns:
        Dataframe of sensors with chip ID, sensor IDs of PM sensors and
            humidity/temperature sensors, address, floor number and side
            of the building that the sensors are installed on

    Raises:
        KeyError if sheet structure does not match listed columns
    """
    sensor_info = retrieve(SENSOR_INFO_CACHE_FILE, SENSOR_SHEET_URL,
                           "InfluencAir sensor information",
                           read_func=pd.read_csv,
                           read_func_kwargs={"header": 1, "dtype": "object"},
                           **retrieval_kwargs)
    try:
        sensor_info = (sensor_info[["Chip ID", "PM Sensor ID",
                                    "Hum/Temp Sensor ID", "Address", "Floor",
                                    "Side (Street/Garden)"]]
                       .rename(columns={"Side (Street/Garden)": "Side"}))
    except KeyError:
        raise KeyError("Could not get columns. Check if the structure or "
                       "labels of the InfluencAir sensor Google Sheet have "
                       "changed.")
    return sensor_info


if __name__ == "__main__":
    sensor_info = get_sensor_info()
