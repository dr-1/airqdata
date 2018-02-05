#!/usr/bin/env python3

"""Get and process air data from IRCELINE-run measuring stations."""

import os

import pandas as pd

from utils import CACHE_DIR, retrieve, haversine

# API URLs
PHENOMENA_URL = "https://geo.irceline.be/sos/api/v1/phenomena"
STATIONS_URL = "https://geo.irceline.be/sos/api/v1/stations"
TIME_SERIES_URL = "https://geo.irceline.be/sos/api/v1/timeseries"
DATA_URL_PATTERN = (TIME_SERIES_URL + "/{time_series_id}/getData?"
                    "timespan={start}/{end}")

# Caching
PHENOMENA_CACHE_FILE = CACHE_DIR + "/irceline_phenomena.json"
STATIONS_CACHE_FILE = CACHE_DIR + "/irceline_stations.json"
TIME_SERIES_CACHE_FILE = CACHE_DIR + "/irceline_time_series.json"


class Metadata:
    """Information about phenomena and stations.

    Properties:
        phenomena: dataframe of measurands, e.g. particulate matter of
            various diameters, nitrogen oxides, ozone; indexed by
            phenomenon ID
        stations: dataframe of station descriptions indexed by station
            ID
        time_series: dataframe of available (station, phenomenon)
            combinations, indexed by (station & phenomenon) ID
    """
    phenomena = None
    stations = None
    time_series = None

    def __init__(self, **retrieval_kwargs):
        """Retrieve metadata through IRCELINE API or from cache.

        Args:
            retrieval_kwargs: keyword arguments to pass to retrieve
                function
        """
        self.get_phenomena(**retrieval_kwargs)
        self.get_stations(**retrieval_kwargs)
        self.get_time_series(**retrieval_kwargs)

    @classmethod
    def get_phenomena(cls, **retrieval_kwargs):
        """Retrieve a list of measured phenomena.

        Args:
            retrieval_kwargs: keyword arguments to pass to retrieve
                function
        """
        phenomena = retrieve(PHENOMENA_CACHE_FILE, PHENOMENA_URL,
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
        stations = retrieve(STATIONS_CACHE_FILE, STATIONS_URL,
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
        time_series = retrieve(TIME_SERIES_CACHE_FILE, TIME_SERIES_URL,
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

        Default values are the approximate center and radius of Brussels.

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


def get_data(time_series, start_date, end_date, **retrieval_kwargs):
    """Retrieve time series data.

    Args:
        time_series: time series ID as listed in Metadata.time_series
        start_date: date string in ISO 8601 format. Interpreted as UTC.
        end_date: date string like start. If the current date or a
            future date is entered, end will be truncated so that only
            complete days are downloaded.
        retrieval_kwargs: keyword arguments to pass to retrieve function

    Returns:
        Dataframe of values, indexed by hourly periods

    Raises:
        ValueError if start_date is later than end_date
    """

    # Make start and end timezone aware and truncate time values
    query_start_date = pd.to_datetime(start_date, format="%Y-%m-%d",
                                      utc=True).normalize()
    query_end_date = pd.to_datetime(end_date, format="%Y-%m-%d",
                                    utc=True).normalize()

    # Check validity of input and truncate end date if needed
    today = pd.to_datetime("today", utc=True)
    yesterday = today - pd.Timedelta(days=1)
    if query_end_date > yesterday:
        # TODO: Raise warning
        query_end_date = yesterday
        end_date = query_end_date.strftime("%Y-%m-%d")
    if query_start_date > query_end_date:
        raise ValueError("end_date must be greater than or equal to "
                         "start_date")

    # IRCELINE API takes local times. Convert start and end accordingly.
    query_start_dt = query_start_date.tz_convert("Europe/Brussels")
    query_start_dt_formatted = query_start_dt.strftime("%Y-%m-%dT%H")
    query_end_dt = query_end_date.tz_convert("Europe/Brussels")
    query_end_dt = (query_end_dt - pd.Timedelta(1, "s"))
    query_end_dt_formatted = query_end_dt.strftime("%Y-%m-%dT%H:%M:%S")

    url = DATA_URL_PATTERN.format(time_series_id=time_series,
                                  start=query_start_dt_formatted,
                                  end=query_end_dt_formatted)

    # TODO: Split response into days and cache as daily files. Also check cache
    #       day by day. Find longest missing intervals to make as few requests
    #       as possible.
    filename = ("irceline_{time_series_id}_{start_date}_{end_date}.json"
                .format(time_series_id=time_series,
                        start_date=start_date, end_date=end_date))
    filepath = os.path.join(CACHE_DIR, filename)

    # TODO: Check day by day if data are cached
    # Retrieve and parse data
    data = retrieve(filepath, url, "IRCELINE timeseries data",
                    **retrieval_kwargs)
    data = pd.DataFrame.from_dict(data.loc[0, "values"])

    # Convert Unix timestamps to datetimes and then to periods for index
    timestamps = pd.to_datetime(data["timestamp"], unit="ms", utc=True)
    periods = timestamps.dt.to_period(freq="h")
    data = pd.Series(data["value"].values, index=periods, dtype="float")

    return data
