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

python3 crawl_torrents.py [-t <timeout_in_sec>] [-f <db_file.sqlite>] [-v]
                          [--peers_count_csv=<csv_file_with_peers_count>]
```

Where:
* `timeout_in_sec` means the time that the experiment will last
* `db_file.sqlite` means the path to `sqlite` db file. 
    If file doesn't exists, then new file will be created. 
    If file exists, then crawler will append it.
* `csv_file_with_peers_count` means the path to `csv` file that contains
    `(time, active_peers, crawled_peers)` tuples.
 

### Example

```
python3 crawl_torrents.py -t 600
python3 crawl_torrents.py -t 600 -f torrents.sqlite
python3 crawl_torrents.py -t 600 -f torrents.sqlite --peers_count_csv="peers.csv"
python3 crawl_torrents.py -t 600 -f torrents.sqlite --peers_count_csv="peers.csv" -v
```

## analyze_crawled_data.py

Source: [analyze_crawled_data.py](analyze_crawled_data.py)

### Description

This script analyzes the crawled data.

As an input it takes `sqlite db`, produced by 
[crawl_torrents.py](crawl_torrents.py).

The result will be stored in a `json` file:
```
[
  {
    "hash": "3f93ae6aabbba6d07176e778d9cbff088e9fbf1d",
    "title": "Ubuntu",
    "count": 224,
    "ratio": 72
  },
  {
    "hash": "95e8d04147f0d9cb8bf00ec8775c926126a65236",
    "title": "Fedora",
    "count": 139,
    "ratio": 44
  },
  {
    "hash": "ba693a610b43a1aa246d3382299775ebdf0fec34",
    "title": "Linux Mint",
    "count": 136,
    "ratio": 43
  }
]
```

and in `csv` file (in a short form):

```
position,node_count,torrent_count,ratio
0,55,39,70
1,55,34,61
2,55,30,54
```


`ratio` is a number, calculated as 

![\Large l](https://latex.codecogs.com/svg.latex?ratio_{i}=\frac{100*count_{i}}{node\\_count})

Where:
 * ![\Large l](https://latex.codecogs.com/svg.latex?ratio_{i})  is a ratio for `i-th torrent`
 * ![\Large l](https://latex.codecogs.com/svg.latex?count_{i})  how many times `i-th torrent` encountered on crawled nodes
 * ![\Large l](https://latex.codecogs.com/svg.latex?node\\_count)  is a count of crawled nodes

### Usage

```
export PYTHONPATH=${PYTHONPATH}:`echo ../.. ../../src/{pyipv8,tribler-common,tribler-core} | tr " " :`

python3 analyze_crawled_data.py [-d <sqlite_db_path>] [-f <json_output_file_path>]
                                [-l <torrent_limit>] [-v]
```

Where:
* `sqlite_db_path` means the path to `sqlite` db file
* `json_output_file_path` means the path to result `json` file. 
Note, there is also a `csv` file that will be produced. It will be located 
on the same path, but with `.csv` extension
* `torrent_limit` is the maximum size of the result set
* `-v` means increase verbosity

 

### Example

```
python3 analyze_crawled_data.py -d crawled_data.sqlite 
python3 analyze_crawled_data.py -d crawled_data.sqlite -f result.json
python3 analyze_crawled_data.py -d crawled_data.sqlite -f result.json -l 100
python3 analyze_crawled_data.py -d crawled_data.sqlite -f result.json -l 100 -v
```