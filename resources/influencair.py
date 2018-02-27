#!/usr/bin/env python3

"""Access InfluencAir resources.

InfluencAir is a project created by Civic Lab Brussels.
"""

import pandas as pd

import luftdaten
import madavi
from utils import CACHE_DIR, retrieve

# Resources
SENSOR_SHEET_URL = ("https://docs.google.com/spreadsheets/d/"
                    "1J8WTKryYjZHfBQrMSYjwj6uLOBmWWLftaTqeicKVfYEv")
SENSOR_SHEET_DOWNLOAD_URL = SENSOR_SHEET_URL + "/export?format=csv"
WEBSITE_URLS = {"https://influencair.be",
                "https://www.meetup.com/Civic-Lab-Brussels"}
MAP_URL = "http://influencair.be/map-brussels/"

# Caching
SENSOR_INFO_CACHE_FILE = CACHE_DIR + "/civic_labs_sensors.csv"


class Metadata:
    """Sensor information as recorded on InfluencAir's Google Sheet.

    Properties:
        sensors: dataframe of sensors with chip ID, sensor IDs of PM
            sensors and humidity/temperature sensors, label, address,
            floor number and side of the building that the sensors are
            installed on
        initialized: boolean to indicate that __init__ has run
    """
    sensors = None
    initialized = False

    @classmethod
    def __init__(cls, **retrieval_kwargs):
        """Retrieve sensor information from the InfluencAir project.

        Args:
            retrieval_kwargs: keyword arguments to pass to retrieve
                function

        Raises:
            KeyError if sheet structure does not match listed columns
        """
        sensor_info = retrieve(SENSOR_INFO_CACHE_FILE,
                               SENSOR_SHEET_DOWNLOAD_URL,
                               "InfluencAir sensor information",
                               read_func=pd.read_csv,
                               read_func_kwargs={"header": 1,
                                                 "dtype": "object"},
                               **retrieval_kwargs)
        try:
            sensor_info = (sensor_info[["Chip ID", "PM Sensor ID",
                                        "Hum/Temp Sensor ID", "Label",
                                        "Address", "Floor",
                                        "Side (Street/Garden)"]]
                           .rename(columns={"Side (Street/Garden)": "Side"}))
        except KeyError:
            raise KeyError("Could not get columns. Check if the structure or "
                           "labels of the InfluencAir sensor Google Sheet "
                           "have changed.")
        cls.sensors = sensor_info
        cls.initialized = True


class Sensor(luftdaten.Sensor):
    """A sensor of the InfluencAir project, registered on
    luftdaten.info.
    """

    def __init__(self, sensor_id, **retrieval_kwargs):
        """Establish sensor properties.

        Properties in addition to those of luftdaten.Sensor:
            luftdaten_metadata_url: metadata_url inherited from parent
                class
            luftdaten_metadata: metadata inherited from parent class
            influencair_metadata: metadata retrieved from InfluencAir's
                Google Sheet
            chip_id: ESP8266 or other chip ID as used by madavi.de API

        Args:
            sensor_id: luftdaten.info sensor id
            retrieval_kwargs: keyword arguments to pass to retrieve
                function
        """
        super().__init__(sensor_id=sensor_id, **retrieval_kwargs)

        # Replace affiliation with combined value
        self.affiliation = "luftdaten.info & InfluencAir"

        self.luftdaten_metadata_url = self.metadata_url
        self.luftdaten_metadata = self.metadata
        self.influencair_metadata = None
        self.chip_id = None
        self.get_influencair_metadata(**retrieval_kwargs)

    def get_influencair_metadata(self, **retrieval_kwargs):
        """Get sensor metadata from InfluencAir's Google Sheet.

        Args:
            retrieval_kwargs: keyword arguments to pass to retrieve
                function

        Raises:
            ValueError if sensor_id is not listed in InfluencAir's
                Google Sheet
        """

        # Ensure that metadata can be queried
        Metadata.initialized or Metadata(**retrieval_kwargs)

        id_match_rows = ((Metadata.sensors["PM Sensor ID"] == self.sensor_id)
                         | (Metadata.sensors["Hum/Temp Sensor ID"]
                            == self.sensor_id))
        if sum(id_match_rows) == 0:
            raise ValueError("Sensor ID {} is not listed in InfluencAir "
                             "metadata sheet".format(self.sensor_id))
        self.influencair_metadata = (Metadata.sensors[id_match_rows].iloc[0]
                                     .drop(labels=["PM Sensor ID",
                                                   "Hum/Temp Sensor ID"]))
        self.chip_id = self.influencair_metadata["Chip ID"]

        # Replace label from parent class with label from Google Sheet
        label = self.influencair_metadata["Label"]
        if label is not pd.np.nan:
            self.label = label

    def get_luftdaten_metadata(self, **retrieval_kwargs):
        """Get sensor metadata and current measurements from cache or
        luftdaten.info API.

        Args:
            retrieval_kwargs: keyword arguments to pass to retrieve
                function

        Warns:
            UserWarning if sensor does not appear to be online
        """
        self.get_metadata(**retrieval_kwargs)
        self.luftdaten_metadata = self.metadata

    def open_madavi_graphs(self):
        """Open madavi.de page showing graphs of the sensor's
        measurement history."""
        if self.sensor_type.lower().startswith("dht"):
            sensor_type = "dht"
        else:
            sensor_type = self.sensor_type.lower()
        madavi.open_graphs(self.chip_id, sensor_model=sensor_type)
