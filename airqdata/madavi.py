#!/usr/bin/env python3

"""Access resources on madavi.de."""

# TODO: Use luftdaten sensor ID instead of madavi chip ID if mapping exists

import webbrowser

GRAPHS_URL_PATTERN = ("https://www.madavi.de/sensor/graph.php?"
                      "sensor=esp8266-{chip_id}-{sensor_model}")


def open_graphs(chip_id, sensor_model="sds011"):
    """Open madavi.de page showing graphs of the measurement history of
    a given chip.

    Args:
        chip_id: ID of the NodeMCU as listed on madavi.de. Note this is
            not the luftdaten.info ID.
        sensor_model: sensor model as it appears in URLs on madavi.de,
            e.g. "sds011" (particulate matter) or "dht" (temperature and
            relative humidity). Case-insensitive in this function.
    """
    url = GRAPHS_URL_PATTERN.format(chip_id=chip_id,
                                    sensor_model=sensor_model.lower())
    webbrowser.open(url)
