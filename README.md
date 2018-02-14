# Air quality data

A toolkit to retrieve, analyze and visualize data from a variety of air quality
sensors.

The scripts include tools to
* wrap the APIs of various data providers, including Civic Lab Brussels'
[InfluencAir](https://influencair.be/) project, the
[luftdaten.info](https://luftdaten.info/) project,
[madavi.de](https://www.madavi.de/ok-lab-stuttgart/) and
[irceline.be](http://www.irceline.be/en)
* clean and combine the retrieved data
* describe measurements statistically - individual sensors or groups to compare
* plot measurement time series
* find sensors that are geographically close

For usage examples, see the
[demo.ipynb](
https://nbviewer.jupyter.org/gist/dr-1/450c275b1ad2cbf88e9c4325c5d032bc)
notebook.

## Requirements
A Python 3.5+ environment is assumed. Several Python packages are required, see
requirements.txt. To install them, use Python's pip command or execute
install_requirements.sh, with elevated privileges
(`sudo ./install_requirements.sh`) if needed on your system.

## Legal
The scripts are licensed under the
[GPLv3](https://www.gnu.org/licenses/gpl-3.0.html).

Data made available by the luftdaten.info project are
[licensed](https://archive.luftdaten.info/00disclamer.md) under the [Open
Database License](https://opendatacommons.org/licenses/odbl/1.0/).

Data published by the Belgian Interregional Environment Agency (IRCEL/CELINE)
are [licensed](http://www.irceline.be/en/documentation/open-data) under the
[Creative Commons Attribution 4.0
license](https://creativecommons.org/licenses/by/4.0/).