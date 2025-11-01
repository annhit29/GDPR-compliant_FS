# Privacy testsuite

This repository contains tools & test cases used to evaluate privacy enforcement architectures.

Developers:

- Anonymous authors

## Structure of the repository

- ``baseline/`` contains the code of the baseline applications without privacy enforcement, written in Python using Flask, SQLite and SQLAlchemy

## Test applications

- **Minitwit** (from Riverbed, *Wang et al.* 2019) is a simple microblogging application

- **Minitwit+** is a fork of Minitwit which additionally displays basic personalized ads

## Installation

``pip3 install -r requirements.html``

## Usage

``python3 privacy_test.py application -f folder [-o option]``

where

- ``application`` is the application to test (Application and Scenario objects defined in ``baseline/application.py``)

- ``folder`` is the output folder in which the data and graphs will be written

- ``option`` may be ``generate`` (no measurements, only generation of graphs; in this case the data file must be located in ``folder/report.csv``) or ``test`` (no generation of graphs)

## FAQ

### I get "OSError: [Errno 24] Too many open files" when performing measurements with a large number of processes

See this page on how to increase the maximal number of open files: 
https://superuser.com/questions/1200539/cannot-increase-open-file-limit-past-4096-ubuntu
