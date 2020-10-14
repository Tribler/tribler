"""This script analyzes the crawled data.

As an input it takes `sqlite db`, produced by crawl_torrents.py

The result will be stored in a `json` file and in a `csv` file (in a short form):
```
[
  {
    "hash": "3f93ae6aabbba6d07176e778d9cbff088e9fbf1d",
    "title": "Ubuntu",
    "count": 224,
    "ratio": 72
  },
  ...,
  {
    ...
  }
]
```

Where:
    * `ratio = 100 * torrent.count / node_count

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
"""
import argparse
import csv
import json
import logging
import math
from pathlib import Path

from pony.orm import Database, db_session

db = Database()
logger = logging.getLogger(__name__)


@db_session
def _get_node_count():
    query = 'select count(distinct peer_hash) as count from RawData'
    logger.info(f'Run query: {query}')
    query_result = db.select(query)
    return query_result[0]


@db_session
def _get_torrent_hash_distribution(limit):
    query = 'select results.torrent_hash, titles.torrent_title, count(results.torrent_hash) as count\n' \
            'from (select distinct torrent_hash, peer_hash from RawData) as results\n' \
            '         join (select distinct torrent_hash, torrent_title from RawData) as titles\n' \
            '              on results.torrent_hash = titles.torrent_hash\n' \
            'group by results.torrent_hash\n' \
            'order by count desc\n' \
            f'limit {limit}'
    logger.info(f'Run query: {query}')
    return db.select(query)


def _save_torrent_hash_distribution(json_file_path, torrent_hash_distribution, node_count):
    result_list = []
    print(f'\nNode count: {node_count}')
    print('ratio')
    for i, torrent in enumerate(torrent_hash_distribution):
        ratio = math.trunc(100 * torrent.count / node_count)
        entity = {
            'position': i,
            'hash': torrent.torrent_hash,
            'title': torrent.torrent_title,
            'count': torrent.count,
            'node_count': node_count,
            'ratio': ratio}
        logger.debug(f'Processing entity: {entity}')
        result_list.append(entity)
        print(f'{i},{node_count},{torrent.count},{ratio}')

    _save_to_json(json_file_path, result_list)
    _save_to_csv(Path(json_file_path).with_suffix('.csv'), result_list)


def _save_to_csv(csv_file_path, result):
    logger.info(f'Saving only "ration" results into {csv_file_path}')
    with csv_file_path.open('w') as f:
        csv_writer = csv.writer(f)
        csv_writer.writerow(['position', 'node_count', 'torrent_count', 'ratio'])
        csv_writer.writerows([e['position'], e['node_count'], e['count'], e['ratio']] for e in result)


def _save_to_json(json_file_path, result):
    logger.info(f'Saving full results into {json_file_path}')
    with open(json_file_path, 'w') as f:
        json.dump(result, f)


def _analyze_results(json_file_path, limit):
    _node_count = _get_node_count()
    _torrent_hash_distribution = _get_torrent_hash_distribution(limit)
    _save_torrent_hash_distribution(json_file_path, _torrent_hash_distribution, _node_count)


def _parse_argv():
    parser = argparse.ArgumentParser(description='Crawl first 100 torrents from random nodes in the network')
    parser.add_argument('-d', '--db', type=str, help='sqlite db file path', default='torrents.sqlite')
    parser.add_argument('-f', '--file', type=str, help='result json file path', default='torrents_distribution.json')
    parser.add_argument('-v', '--verbosity', help='increase output verbosity', action='store_true')
    parser.add_argument('-l', '--limit', type=int, help='count (limit) of torrents in the output list', default=50)

    return parser.parse_args()


if __name__ == "__main__":
    _arguments = _parse_argv()
    print(f"Arguments: {_arguments}")

    logging_level = logging.DEBUG if _arguments.verbosity else logging.CRITICAL
    logging.basicConfig(level=logging_level)

    db.bind('sqlite', _arguments.db)
    db.generate_mapping(check_tables=True)

    _analyze_results(_arguments.file, _arguments.limit)
