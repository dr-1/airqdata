# Air quality data

A toolkit to retrieve, analyze and visualize data from a variety of air quality
sensors.

The scripts include tools to  
* wrap the APIs of various data providers, including Civic Lab Brussels'
[InfluencAir] project, the [luftdaten.info] project, [madavi.de] and
[irceline.be]  
* represent sensors of those different providers as objects with a unified
  interface to make it easy to interact with them  
* retrieve sensor measurement data through API calls  
* cache those data  
* clean and combine the data  
* describe measurements statistically - individual sensors or groups to
  compare  
* plot measurement time series  
* find sensors that are geographically close to a point of interest or to other
  sensors  

For usage examples, see the [demo] notebook.

## Installation
To install airqdata from PyPI, run  
`pip install airqdata`

A Python 3.5+ environment and several Python packages are required. When
installing airqdata with pip, those dependencies will be installed
automatically. Otherwise see requirements.txt and
install_requirements.sh in this repository.

## Legal
The scripts are licensed under the [GPLv3].

Data made available by the luftdaten.info project are [licensed][luftdaten
licensing] under the [Open Database License][ODbL].

Data published by the Belgian Interregional Environment Agency (IRCEL/CELINE)
are [licensed][irceline licensing] under the [Creative Commons Attribution 4.0
license][CC-BY 4.0].

[InfluencAir]: https://influencair.be
[luftdaten.info]: https://luftdaten.info
[madavi.de]: https://www.madavi.de/ok-lab-stuttgart
[irceline.be]: http://www.irceline.be/en
[demo]: https://nbviewer.jupyter.org/gist/dr-1/450c275b1ad2cbf88e9c4325c5d032bc
[GPLv3]: https://www.gnu.org/licenses/gpl-3.0.html
[luftdaten licensing]: https://archive.luftdaten.info/00disclamer.md
[ODbL]: https://opendatacommons.org/licenses/odbl/1.0/
[irceline licensing]: http://www.irceline.be/en/documentation/open-data
[CC-BY 4.0]: https://creativecommons.org/licenses/by/4.0
