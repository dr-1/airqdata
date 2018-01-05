# Air quality data

These scripts retrieve and process air quality data, mainly on particulate
matter, for the Civic Labs Belgium air quality project.

They
* wrap the APIs of various sources, including Civic Labs Belgium's Google
Sheets, luftdaten.info, madavi.de and irceline.be
* clean and combine the retrieved data
* analyze and visualize the data

The [demo.ipynb](https://github.com/dr-1/airqdata/blob/master/demo.ipynb)
notebook shows how the modules can be used.

## Requirements
A Python 3.5+ environment is assumed. Several Python packages are required, see
requirements.txt. To install them, use Python's pip command or execute
install_requirements.sh, with elevated privileges
(`sudo ./install_requirements.sh`) if needed on your system.

## Legal
The scripts are licensed under the
[GPLv3](https://www.gnu.org/licenses/gpl-3.0.html).

Some of the scripts make use of data published by the Belgian Interregional
Environment Agency (IRCEL/CELINE) under the [Creative Commons Attribution 4.0
license](https://creativecommons.org/licenses/by/4.0/).