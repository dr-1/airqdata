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
PROX_PARAM_PATTERN = ('near={{"center":{{"type":"Point",'
                      '"coordinates":[{lon},{lat}]}},"radius":{radius}}}')
PHENOMENON_PARAM_PATTERN = "phenomenon={phenomenon}"
PROX_SEARCH_URL_PATTERN = ('https://geo.irceline.be/sos/api/v1/stations?'
                           'near={{"center":{{"type":"Point",'
                           '"coordinates":[{lon},{lat}]}},"radius":{radius}}}')

# Caching
PHENOMENA_CACHE_FILE = CACHE_DIR + "/irceline_phenomena.json"
STATIONS_CACHE_FILE_PATTERN = CACHE_DIR + "/irceline_stations{params}.json"
TIME_SERIES_CACHE_FILE = CACHE_DIR + "/irceline_time_series.json"
PROX_CACHE_FILE_PATTERN = (CACHE_DIR +
                           "/irceline_prox_{lat}_{lon}_{radius}.json")


class Metadata:
    """Information about phenomena and stations."""

    def __init__(self, phenomenon=None, location=None, **retrieval_kwargs):
        """Collect information through IRCELINE API or from cache.

        Args:
            phenomenon: measured phenomenon to filter stations for
            location: dict like
                {"lat": lat, "lon": lon, "radius": radius} to filter by
                geographic proximity; see search_proximity
            retrieval_kwargs: keyword arguments to pass to retrieve
                function

        Properties in addition to those constructed from arguments:
            phenomena: dataframe of measurands, e.g. particulate matter
                of various diameters, nitrogen oxides, ozone; indexed by
                phenomenon ID
            categories: same as phenomena
            stations: dataframe of station descriptions indexed by
                station ID
            pm_stations: dataframe of stations that measure particulate
                matter
            time_series: dataframe of available (station, phenomenon)
                combinations, indexed by (station & phenomenon) ID
        """

        # Properties from arguments
        self.phenomenon = phenomenon
        self.location = location

        self.phenomena = None
        self.stations = None
        self.time_series = None
        self.get_phenomena(**retrieval_kwargs)
        self.get_stations(**retrieval_kwargs)
        self.get_time_series(**retrieval_kwargs)

    def get_phenomena(self, **retrieval_kwargs):
        """Retrieve a list of measured phenomena.

        Args:
            retrieval_kwargs: keyword arguments to pass to retrieve
                function
        """
        phenomena = retrieve(PHENOMENA_CACHE_FILE, PHENOMENA_URL,
                             "phenomenon metadata", **retrieval_kwargs)
        # FIXME: id not converted to int
        phenomena.set_index("id", inplace=True)
        phenomena.sort_index(inplace=True)
        self.phenomena = phenomena

    @property
    def categories(self):
        """Same as phenomena."""
        return self.phenomena

    def get_stations(self, **retrieval_kwargs):
        """Retrieve a list of measuring stations.

        Args:
            retrieval_kwargs: keyword arguments to pass to retrieve
                function
        """

        # Build query URL and cache file name
        search_params = sum((self.phenomenon is not None,
                             self.location is not None))
        url = STATIONS_URL + (search_params > 0) * "?"
        cache_file_params = (search_params > 0) * "_"
        if self.phenomenon is not None:
            search_params -= 1
            url += PHENOMENON_PARAM_PATTERN.format(phenomenon=self.phenomenon)
            url += (search_params > 0) * "&"
            cache_file_params += (str(self.phenomenon)
                                  + (search_params > 0) * "_")
        if self.location is not None:
            url += PROX_PARAM_PATTERN.format(**self.location)
            cache_file_params += ("{lon}_{lat}_{radius}"
                                  .format(**self.location).replace(".", "-"))
        pattern = STATIONS_CACHE_FILE_PATTERN
        cache_file = pattern.format(params=cache_file_params)

        # Retrieve and reshape data
        stations = retrieve(cache_file, url, "station metadata",
                            **retrieval_kwargs)
        stations.drop(columns=["geometry.type", "type"], inplace=True)
        stations.rename(columns={"properties.id": "id",
                                 "properties.label": "label"}, inplace=True)
        stations.set_index("id", inplace=True)

        # Split coordinates into columns
        coords = pd.DataFrame([row
                               for row in stations["geometry.coordinates"]],
                              index=stations.index)
        stations[["lon", "lat", "alt"]] = coords
        stations.drop(columns=["geometry.coordinates", "alt"], inplace=True)

        self.stations = stations

    def get_time_series(self, **retrieval_kwargs):
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
        time_series.set_index("id", inplace=True)
        time_series.drop(columns=["station.geometry.type", "station.type"],
                         inplace=True)
        time_series.rename(columns={"station.properties.id": "station_id",
                                    "station.properties.label":
                                        "station_label",
                                    "uom": "unit"},
                           inplace=True)

        # Extract phenomenon names from labels
        labels = time_series["label"]
        time_series["phenomenon"] = labels.apply(get_phenomenon_name)

        # Split coordinates into columns
        coords = pd.DataFrame([row
                               for row
                               in time_series["station.geometry.coordinates"]],
                              index=time_series.index)
        time_series[["station_lon", "station_lat", "station_alt"]] = coords

        # Sort and drop columns
        time_series = time_series[["label", "phenomenon", "unit",
                                   "station_id", "station_label",
                                   "station_lon", "station_lat"]]

        self.time_series = time_series

    def list_stations_by_phenomenon(self, phenomenon):
        """Get a list of stations that measure a given phenomenon.

        Args:
            phenomenon: name of the phenomenon, case-insensitive

        Returns:
            Subset of self.stations
        """
        if self.time_series is None:
            self.get_time_series()
        phenomena_lower = self.time_series["phenomenon"].str.lower()
        matching_time_series = phenomena_lower == phenomenon.lower()
        matching_station_ids = (self.time_series
                                .loc[matching_time_series, "station_id"]
                                .unique())
        matching_stations = self.stations.loc[matching_station_ids]
        return matching_stations

    @property
    def pm10_stations(self):
        """Get a list of stations that measure PM10.

        Returns:
            Subset of self.stations
        """
        return self.list_stations_by_phenomenon("Particulate Matter < 10 µm")

    @property
    def pm25_stations(self):
        """Get a list of stations that measure PM2.5.

        Returns:
            Subset of self.stations
        """
        return self.list_stations_by_phenomenon("Particulate Matter < 2.5 µm")

    def get_stations_by_name(self, name):
        """Get stations matching a station name.

        Args:
            name: full or partial station name; case-insensitive

        Returns:
            Matching subset of self.stations
        """
        station_labels_lower = self.stations["label"].str.lower()
        matching = station_labels_lower.str.contains(name.lower())
        return self.stations[matching]

    def list_station_time_series(self, station):
        """List available time series for a station.

        Args:
            station: full or partial station name, case-insensitive

        Returns:
            Matching subset of self.time_series
        """
        station_ids = self.get_stations_by_name(station).index
        _filter = self.time_series["station_id"].isin(station_ids)
        return (self.time_series[_filter]
                .drop(columns=["station_lon", "station_lat"]))

    def search_proximity(self, lat=50.848, lon=4.351, radius=8):
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
        metadata. The irceline.be API offers an alternative way to get
        an (unordered) list of stations near a location, see
        PROX_SEARCH_URL_PATTERN.
        """
        near_stations = self.stations.copy()
        near_stations["distance"] = (near_stations
                                     .apply(lambda x:
                                            haversine(lon, lat,
                                                      x["lon"], x["lat"]),
                                            axis=1))
        near_stations = near_stations[near_stations["distance"] <= radius]
        near_stations.sort_values("distance", inplace=True)
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
