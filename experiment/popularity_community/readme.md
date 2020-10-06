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
export PYTHONPATH=${PYTHONPATH}:`echo ../../src/{pyipv8,tribler-common,tribler-core} | tr " " :`

python3 initial_filling.py [-i <check_interval_in_sec>] [-t <timeout_in_sec>] [-f <output_file.csv>]
```

Where:
* `check_interval_in_sec` means how frequently we check the torrent list
* `timeout_in_sec` means a time that the experiment will last
* `output_file.csv` means a path and a result file name 

### Example

```
python3 initial_filling.py -i 60
python3 initial_filling.py -i 60 -t 900
python3 initial_filling.py -i 60 -t 900 -f result.csv
```

## crawl_torrents.py

Source: [crawl_torrents.py](crawl_torrents.py)

### Description

This script crawl first 50 torrents from random nodes in the network.

Result will be stored in a json file:
```
{
  "3409ac2015b264f77c35a694c7a2f28794944de1": [
    [
      21,
      "69a949f0c162314cd0fa1dca6ced91fb6409a9c7",
      "Collection1"
    ],
    [
      2,
      "738108f29a5783b8e8f341de498f3b50089cdee7",
      "Favorite Torrents"
    ],
    [
      29,
      "f58ed7d43b6ea56d092060304cbcb29ec17df274",
      "Ubuntu"
    ],
  ],
  "618acf017f802d429a0c0af7910efd1fc57c9134": [
    [
      2,
      "bafa14cd54c28a25f189cb2e877160803aa7ada4",
      "My collection"
    ]
  ],
  "fa21132cb45a30137473dc2728015f089685807a": [
    [
      44,
      "99ea9de71f25916331378731c2e8742f4611725e",
      "SomeTorrents"
    ]
  ]
}
```

Where tuples are:
* votes
* infohash
* title

### Usage

```
export PYTHONPATH=${PYTHONPATH}:`echo ../../src/{pyipv8,tribler-common,tribler-core} | tr " " :`

python3 crawl_torrents.py [-t <timeout_in_sec>] [-f <output_file.json>]
```

Where:
* `timeout_in_sec` means a time that the experiment will last
* `output_file.json` means a path and a result file name 

### Example

```
python3 crawl_torrents.py -t 600
python3 crawl_torrents.py -t 600 -f result.json
```