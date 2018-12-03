#!/usr/bin/env python3

"""Get and process air data from IRCELINE-run measuring stations."""

import os
import warnings
import time
from itertools import chain

import pandas as pd

from airqdata.utils import (EQUIVALENT_PHENOMENA, BaseSensor, cache_dir,
                            retrieve, haversine)

# API
API_DOCUMENTATION_URL = "https://geo.irceline.be/sos/static/doc/api-doc/"
API_BASE_URL = "https://geo.irceline.be/sos/api/v1/"
API_ENDPOINTS = {"phenomena": API_BASE_URL + "phenomena",
                 "stations": API_BASE_URL + "stations",
                 "timeseries": API_BASE_URL + "timeseries",
                 "data pattern":
                 API_BASE_URL + ("timeseries/{time_series_id}/getData?"
                                 "timespan={start}/{end}")}

# Other resources
WEBSITE_URL = "http://www.irceline.be"
VIEWER_URL = "http://viewer.irceline.be"


class Metadata:
    """Information about phenomena and stations.

    Properties:
        phenomena: dataframe of phenomena, e.g. particulate matter of
            various diameters, nitrogen oxides, ozone; indexed by
            phenomenon ID
        stations: dataframe of station descriptions indexed by station
            ID
        time_series: dataframe of available (station, phenomenon)
            combinations, indexed by (station & phenomenon) ID
        initialized: boolean to indicate that __init__ has run
    """
    phenomena = None
    stations = None
    time_series = None
    initialized = False

    @classmethod
    def __init__(cls, **retrieval_kwargs):
        """Retrieve metadata through IRCELINE API or from cache.

        Args:
            retrieval_kwargs: keyword arguments to pass to retrieve
                function
        """
        cls.get_phenomena(**retrieval_kwargs)
        cls.get_stations(**retrieval_kwargs)
        cls.get_time_series(**retrieval_kwargs)
        cls.initialized = True

    @classmethod
    def get_phenomena(cls, **retrieval_kwargs):
        """Retrieve a list of measured phenomena.

        Args:
            retrieval_kwargs: keyword arguments to pass to retrieve
                function
        """
        phenomena = retrieve(phenomena_cache_file, API_ENDPOINTS["phenomena"],
                             "phenomenon metadata", **retrieval_kwargs)
        phenomena["id"] = phenomena["id"].astype("int")
        phenomena = phenomena.set_index("id").sort_index()
        cls.phenomena = phenomena

    @classmethod
    def get_stations(cls, **retrieval_kwargs):
        """Retrieve a list of measuring stations.

        Args:
            retrieval_kwargs: keyword arguments to pass to retrieve
                function
        """

        # Retrieve and reshape data
        stations = retrieve(stations_cache_file, API_ENDPOINTS["stations"],
                            "station metadata", **retrieval_kwargs)
        stations = (stations
                    .drop(columns=["geometry.type", "type"])
                    .rename(columns={"properties.id": "id",
                                     "properties.label": "label"})
                    .set_index("id"))

        # Split coordinates into columns
        coords = pd.DataFrame([row
                               for row in stations["geometry.coordinates"]],
                              index=stations.index)
        stations[["lat", "lon"]] = coords[[1, 0]]
        stations.drop(columns=["geometry.coordinates"], inplace=True)

        cls.stations = stations

    @classmethod
    def get_time_series(cls, **retrieval_kwargs):
        """Retrieve information on available time series: a collection
        of station & phenomenon combinations.

        Args:
            retrieval_kwargs: keyword arguments to pass to retrieve
                function
        """

        def get_phenomenon_name(label):
            """Extract phenomenon name from time series label."""
            phenomenon_name_series_id = (label
                                         .split(sep=" - ", maxsplit=1)[0])
            phenomenon_name = phenomenon_name_series_id.rsplit(maxsplit=1)[0]
            return phenomenon_name

        # Retrieve and reshape data
        time_series = retrieve(time_series_cache_file,
                               API_ENDPOINTS["timeseries"],
                               "time series metadata", **retrieval_kwargs)
        time_series["id"] = time_series["id"].astype("int")
        time_series = (time_series
                       .set_index("id")
                       .drop(columns=["station.geometry.type",
                                      "station.type"])
                       .rename(columns={"station.properties.id": "station_id",
                                        "station.properties.label":
                                            "station_label",
                                        "uom": "unit"}))

        # Extract phenomenon names from labels
        labels = time_series["label"]
        time_series["phenomenon"] = labels.apply(get_phenomenon_name)

        # Split coordinates into columns
        coords = pd.DataFrame([row
                               for row
                               in time_series["station.geometry.coordinates"]],
                              index=time_series.index)
        time_series[["station_lat", "station_lon"]] = coords[[1, 0]]

        # Sort and drop columns
        time_series = time_series[["label", "phenomenon", "unit",
                                   "station_id", "station_label",
                                   "station_lat", "station_lon"]]

        # Clean unit descriptors
        time_series["unit"] = (time_series["unit"]
                               .str.replace("m3", "m³")
                               .str.replace("ug", "µg"))
        (time_series
         .loc[time_series["phenomenon"] == "temperature", "unit"]) = "°C"

        cls.time_series = time_series

    @classmethod
    def query_time_series(cls, phenomenon, lat_nearest=None, lon_nearest=None):
        """Convenience method to filter time series for those that
        measure a given phenomenon, and sort by distance to a point if
        given.

        Args:
            phenomenon: character sequence or regular expression to
                filter phenomena by; operates on the "phenomenon" column
                of the time_series dataframe
            lat_nearest: latitude of the reference point
            lon_nearest: longitude of the reference point

        Returns:
            Subset of time_series property. If lat_nearest and
                lon_nearest are given, the result has an additional
                column indicating distance in km from that point, and is
                sorted by that distance.

        Raises:
            ValueError if only one of lat_nearest, lon_nearest is given
        """
        if bool(lat_nearest is None) != bool(lon_nearest is None):
            raise ValueError("Provide both or none of lat_nearest, "
                             "lon_nearest")
        phenomena_lower = cls.time_series["phenomenon"].str.lower()
        matches = phenomena_lower.str.contains(phenomenon.lower())
        results = cls.time_series[matches].copy()
        if lat_nearest is None:
            return results
        if len(results) == 0:
            results["distance"] = None
            return results
        results["distance"] = results.apply(lambda row:
                                            haversine(lat_nearest, lon_nearest,
                                                      row["station_lat"],
                                                      row["station_lon"]),
                                            axis=1)
        results = results.sort_values("distance")
        return results

    @classmethod
    def get_pm10_time_series(cls):
        """Get the subset of time series related to PM10.

        Returns:
            Subset of time_series property
        """
        return cls.query_time_series("Particulate Matter < 10 µm")

    @classmethod
    def get_pm25_time_series(cls):
        """Get the subset of time series related to PM2.5.

        Returns:
            Subset of time_series property
        """
        return cls.query_time_series("Particulate Matter < 2.5 µm")

    @classmethod
    def get_stations_by_name(cls, name):
        """Get stations matching a station name.

        Args:
            name: full or partial station name; case-insensitive

        Returns:
            Matching subset of stations property
        """
        station_labels_lower = cls.stations["label"].str.lower()
        matching = station_labels_lower.str.contains(name.lower())
        return cls.stations[matching]

    @classmethod
    def list_station_time_series(cls, station):
        """List available time series for a station.

        Args:
            station: full or partial station name, case-insensitive

        Returns:
            Matching subset of time_series property
        """
        station_ids = cls.get_stations_by_name(station).index
        _filter = cls.time_series["station_id"].isin(station_ids)
        return (cls.time_series[_filter]
                .drop(columns=["station_lat", "station_lon"]))

    @classmethod
    def search_proximity(cls, lat=50.848, lon=4.351, radius=8):
        """List stations within given radius from a location.

        Args:
            lat: latitude of the center of search, in decimal degrees
            lon: longitude of the center of search, in decimal degrees
            radius: maximum distance from center, in kilometers

        Default values are the approximate center and radius of
        Brussels.

        Returns:
            Dataframe of matching stations, listing sensor types,
                locations and distances in kilometers from the search
                center, indexed by station ID

        The search is based on the station list retrieved as part of the
        metadata.

        The irceline.be API offers an alternative way to get an
        (unordered) list of stations near a location:
        `https://geo.irceline.be/sos/api/v1/stations?
        near={{"center":{{"type":"Point","coordinates":[{lon},
        {lat}]}},"radius":{radius}}}`
        """
        near_stations = cls.stations.copy()
        near_stations["distance"] = (near_stations
                                     .apply(lambda x:
                                            haversine(lat, lon,
                                                      x["lat"], x["lon"]),
                                            axis=1))
        near_stations = (near_stations[near_stations["distance"] <= radius]
                         .sort_values("distance"))
        return near_stations


class Sensor(BaseSensor):
    """A sensor located at an IRCELINE measuring station.

    Sensors are represented as time series by IRCELINE.
    """

    def __init__(self, timeseries_id):
        """Establish sensor properties.

        Args:
            timeseries_id: IRCELINE time series ID as listed in
                Metadata.time_series, used as value of sensor_id
                property
        """

        # Ensure that metadata can be queried
        Metadata.initialized or Metadata()

        super().__init__(sensor_id=timeseries_id, affiliation="IRCELINE")
        self.metadata = Metadata.time_series.loc[int(timeseries_id)]
        self.label = "at " + self.metadata["station_label"]
        self.lat = self.metadata["station_lat"]
        self.lon = self.metadata["station_lon"]
        self.phenomena = [self.metadata["phenomenon"]]
        self.units = {self.metadata["phenomenon"]: self.metadata["unit"]}

    def get_measurements(self, start_date, end_date, **retrieval_kwargs):
        """Retrieve time series data.

        Args:
            start_date: date string in ISO 8601 (YYYY-MM-DD) format.
                Interpreted as UTC.
            end_date: date string like start_date. If the current date
                or a future date is entered, end will be truncated so
                that only complete days are downloaded.
            retrieval_kwargs: keyword arguments to pass to retrieve
                function

        Raises:
            ValueError if start_date is later than end_date
        """

        # Make start and end timezone aware and truncate time values
        query_start_date = pd.to_datetime(start_date, format="%Y-%m-%d",
                                          utc=True).normalize()
        query_end_date = (pd.to_datetime(end_date, format="%Y-%m-%d",
                                         utc=True).normalize()
                          + pd.Timedelta(days=1))  # To include end_date data

        # Check validity of input and truncate end date if needed
        today = pd.to_datetime("today", utc=True)
        if query_end_date > today:
            warnings.warn("Resetting end_date to yesterday")
            yesterday = today - pd.Timedelta(days=1)
            end_date = yesterday.strftime("%Y-%m-%d")
            query_end_date = today  # 00:00, to include yesterday's data
        if query_start_date > query_end_date:
            raise ValueError("end_date must be greater than or equal to "
                             "start_date")

        # IRCELINE API takes local times. Convert start and end accordingly.
        query_start_local = query_start_date.tz_convert("Europe/Brussels")
        query_start_local_str = query_start_local.strftime("%Y-%m-%dT%H")
        query_end_local = query_end_date.tz_convert("Europe/Brussels")
        query_end_local -= pd.Timedelta(1, "s")
        query_end_local_str = query_end_local.strftime("%Y-%m-%dT%H:%M:%S")

        url = (API_ENDPOINTS["data pattern"]
               .format(time_series_id=self.sensor_id,
                       start=query_start_local_str,
                       end=query_end_local_str))

        # TODO: Split response into days and cache as daily files; check cache
        #       day by day. Find longest missing intervals to make as few
        #       requests as possible.
        filename = ("irceline_{time_series_id}_{start_date}_{end_date}.json"
                    .format(time_series_id=self.sensor_id,
                            start_date=start_date, end_date=end_date))
        filepath = os.path.join(cache_dir, filename)

        # TODO: Check day by day if data are cached
        # Retrieve and parse data
        data = retrieve(filepath, url, "IRCELINE timeseries data",
                        **retrieval_kwargs)
        data = pd.DataFrame.from_dict(data.loc[0, "values"])
        if len(data) == 0:
            return
        data["value"] = data["value"].astype("float")
        data = data.rename(columns={"value": self.metadata["phenomenon"]})

        # Convert Unix timestamps to datetimes and then to periods for index
        data.index = (pd.to_datetime(data["timestamp"], unit="ms", utc=True)
                      .dt.to_period(freq="h"))
        data.index.name = "Period"
        data = data.drop(columns=["timestamp"])

        self.measurements = data

    def get_latest_measurement(self, **retrieval_kwargs):
        """Retrieve time series data.

        Args:
            retrieval_kwargs: keyword arguments to pass to retrieve
                function
        """

        sensor_id = self.sensor_id

        # Make start and end timezone aware and truncate time values
        today = time.strftime("%Y-%m-%d")
        tomorrow_date = pd.to_datetime(today, format="%Y-%m-%d",
                                       utc=True).normalize() + \
                        pd.Timedelta(days=1)
        tomorrow = tomorrow_date.strftime("%Y-%m-%d")

        # download the data
        url = (API_ENDPOINTS["data pattern"]
               .format(time_series_id=sensor_id,
                       start=today,
                       end=tomorrow))

        filename = ("irceline_{time_series_id}_{start_date}_{end_date}.json"
                    .format(time_series_id=sensor_id,
                            start_date=today, end_date=tomorrow))
        filepath = os.path.join(cache_dir, filename)

        # Retrieve and parse data
        data = retrieve(filepath, url, "IRCELINE timeseries data",
                        **retrieval_kwargs)
        data = pd.DataFrame.from_dict(data.loc[0, "values"])
        data = data[data['value'] != "NaN"]
        data = data.tail(1)
        last_measurement = data['value'].iloc[0]

        self.measurements = last_measurement

    def clean_measurements(self):
        """Clean measurement data."""
        pass

    def get_hourly_means(self):
        """Get hourly means of measurements. In IRCELINE time series
        these are identical to hourly means.

        Returns:
            measurements property
        """
        return self.measurements

    def plot_measurements(self, show=True):
        """Plot hourly means. In IRCELINE time series these are
        identical to measurements.

        Args:
            call plt.show; set to False to modify plots

        Returns:
            List of Matplotlib figures
            List of Matplotlib axes
        """
        return self.plot_hourly_means(show=show)


def find_nearest_sensors(sensor, **retrieval_kwargs):
    """For a given sensor of any affiliation, find the nearest IRCELINE
        sensors that measure equivalent phenomena.

    Args:
        sensor: sensor object, instance of utils.BaseSensor
        retrieval_kwargs: keyword arguments to pass to retrieve function

    Returns:
        Dataframe of information on nearest matching IRCELINE sensor
    """

    # Ensure that IRCELINE metadata can be queried
    Metadata.initialized or Metadata(**retrieval_kwargs)

    nearest = pd.DataFrame()
    for phenomenon in sensor.phenomena:

        # Names of comparable phenomena potentially measured by IRCELINE
        equivalent_phenomena = chain.from_iterable(group
                                                   for group
                                                   in EQUIVALENT_PHENOMENA
                                                   if phenomenon in group)

        # Collect and combine matching IRCELINE time series
        matching_pieces = []
        for equivalent_phenomenon in equivalent_phenomena:
            matching_piece = Metadata.query_time_series(equivalent_phenomenon,
                                                        lat_nearest=sensor.lat,
                                                        lon_nearest=sensor.lon)
            matching_pieces.append(matching_piece)
        try:
            results = pd.concat(matching_pieces).sort_values("distance")
        except ValueError:  # No matching time series
            continue

        # Pick nearest
        first_result = (results
                        .reset_index()
                        .iloc[0]
                        .rename({"id": "time series id"}))
        nearest[phenomenon] = first_result

    return nearest


# Caching
phenomena_cache_file = os.path.join(cache_dir, "irceline_phenomena.json")
stations_cache_file = os.path.join(cache_dir, "irceline_stations.json")
time_series_cache_file = os.path.join(cache_dir, "irceline_time_series.json")
