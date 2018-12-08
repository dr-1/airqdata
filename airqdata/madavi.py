#!/usr/bin/env python3

"""Access resources on madavi.de."""

import webbrowser

from airqdata import utils

GRAPHS_URL_PATTERN = ("https://www.madavi.de/sensor/graph.php?"
                      "sensor=esp8266-{chip_id}-{sensor_model}")


def open_graphs(chip_id, sensor_model="sds011"):
    """Open madavi.de page showing graphs of the measurement history of
    a given chip.

    Args:
        chip_id: ID of the NodeMCU as listed on madavi.de. Note this is
            not the luftdaten.info sensor ID. No complete mapping
            between chip IDs and sensor IDs exists at the moment.
        sensor_model: sensor model as it appears in URLs on madavi.de,
            e.g. "sds011" (particulate matter) or "dht" (temperature and
            relative humidity). Case-insensitive in this function.
    """
    url = GRAPHS_URL_PATTERN.format(chip_id=chip_id,
                                    sensor_model=sensor_model.lower())
    call_rate_limiter()
    webbrowser.open(url)


call_rate_limiter = utils.CallRateLimiter()
