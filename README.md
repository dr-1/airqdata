# Air quality data

A toolkit to retrieve, analyze and visualize data from a variety of air quality
sensors.

The scripts include tools to
* wrap the APIs of various data providers, including Civic Labs Belgium's
InfluencAir project, the luftdaten.info project, madavi.de and irceline.be
* clean and combine the retrieved data
* describe measurements statistically - individual sensors or groups to compare
* plot measurement time series
* find sensors that are geographically close


For usage examples, see the
[demo.ipynb](https://github.com/dr-1/airqdata/blob/master/demo.ipynb) notebook.

Note that the API will evolve considerably over the coming weeks. In
particular, BaseSensor and BaseStation template classes will be introduced for
a cleaner and more consistent model of those real-world objects. This will make
it easier to compare sensors that belong to different organizations.

## Requirements
A Python 3.5+ environment is assumed. Several Python packages are required, see
requirements.txt. To install them, use Python's pip command or execute
install_requirements.sh, with elevated privileges
(`sudo ./install_requirements.sh`) if needed on your system.

## Legal
The scripts are licensed under the
[GPLv3](https://www.gnu.org/licenses/gpl-3.0.html).

Data published by the Belgian Interregional Environment Agency (IRCEL/CELINE)
are licensed under the [Creative Commons Attribution 4.0 license]
(https://creativecommons.org/licenses/by/4.0/).