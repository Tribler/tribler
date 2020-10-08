# Set of experiments on Popularity Community

## initial_filling.py

Issue: https://github.com/Tribler/tribler/issues/5580

* Raw result data from the last build: 
[result.csv](https://jenkins-ci.tribler.org/job/popularity_experiments/job/Initial_filling_velocity/lastSuccessfulBuild/artifact/result.csv/*view*/)

* Build-to-build visualisation: 
[plot in Jenkins](https://jenkins-ci.tribler.org/job/popularity_experiments/job/Initial_filling_velocity/plot/)

* Jenkins 
[job](https://jenkins-ci.tribler.org/job/popularity_experiments/job/Initial_filling_velocity/) 

Source: [initial_filling.py](initial_filling.py)

### Description

This script calculate velocity of torrents list filling.

Given: the real network.

Action: 
* add a new node
* every `N` seconds check how long torrent's list are

Result will be stored in a csv file:
```
time_in_sec,total,alive 
10,313,27 
20,313,27 
30,320,27 
```

### Usage

```
export PYTHONPATH=${PYTHONPATH}:`echo ../.. ../../src/{pyipv8,tribler-common,tribler-core} | tr " " :`

python3 initial_filling.py [-i <check_interval_in_sec>] [-t <timeout_in_sec>] [-f <output_file.csv>]
```

Where:
* `check_interval_in_sec` means how frequently we check the torrent list
* `timeout_in_sec` means the time that the experiment will last
* `output_file.csv` means the path to a result file  

### Example

```
python3 initial_filling.py -i 60
python3 initial_filling.py -i 60 -t 900
python3 initial_filling.py -i 60 -t 900 -f result.csv
```

## crawl_torrents.py

Source: [crawl_torrents.py](crawl_torrents.py)

### Description

This script crawl first 100 torrents from random nodes in the network.

Result will be stored in a `sqlite` db:
```
class RawData(db.Entity):
    peer_hash = Required(str)
    torrent_hash = Required(str)
    torrent_title = Required(str)
    torrent_votes = Required(int)
    torrent_position = Required(int)
    date_add = Required(datetime)
```

Where:
* `position` is a torrent's rank inside single `query response`, ordered by `HEALTH`

### Usage

```
export PYTHONPATH=${PYTHONPATH}:`echo ../.. ../../src/{pyipv8,tribler-common,tribler-core} | tr " " :`

python3 crawl_torrents.py [-t <timeout_in_sec>] [-f <db_file.sqlite>]
```

Where:
* `timeout_in_sec` means the time that the experiment will last
* `db_file.sqlite` means the path to `sqlite` db file. 
    If file doesn't exists, then new file will be created. 
    If file exists, then crawler will append it.
 

### Example

```
python3 crawl_torrents.py -t 600
python3 crawl_torrents.py -t 600 -f torrents.sqlite
```