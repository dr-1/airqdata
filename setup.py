#!/usr/bin/env python3

"""Setup module for airqdata."""

import os
from setuptools import find_packages, setup

# Get short and long descriptions from readme file
here = os.path.abspath(os.path.dirname(__file__))
readme_file = os.path.join(here, "README.md")
line = ""
with open(readme_file, "r") as file:
    while line.startswith("#") or not line.strip():
        line = file.readline()
    short_description = line.strip()
    long_description = line + file.read()

setup(name="airqdata",
      version="0.1",
      description=short_description,
      long_description=long_description,
      long_description_content_type="text/markdown",
      url="https://github.com/dr-1/airqdata",
      author="Dominik Rubo",
      license="GNU GPLv3",
      classifiers=[
          "Development Status :: 3 - Alpha",
          "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
          "Operating System :: OS Independent",
          "Programming Language :: Python :: 3",
          "Programming Language :: Python :: 3.5",
          "Programming Language :: Python :: 3.6",
          "Programming Language :: Python :: 3.7",
          "Topic :: Scientific/Engineering :: Information Analysis",
      ],
      keywords=("air quality pollution sensor data analysis particulate "
                "matter pm influencair irceline luftdaten"),
      packages=find_packages(),
      install_requires=[
          "matplotlib>=2",
          "pandas>=0.22",
          "requests>=2.10",
      ],
      python_requires=">=3.5",
      )
