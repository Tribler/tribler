# Seedbox

This folder contains scripts for effortlessly setting up a seedbox.

The seedbox consists of two parts:

1. Torrent seeding (by using a LibTorrent protocol)
1. Channel disseminating (by using the Tribler network)

## Prerequisites

1. Clone the tribler repo include sub modules:
    ```shell
    git clone --recursive https://github.com/Tribler/tribler.git
    ```
1. Install requirements:
    ```bash
    python3 -m pip install -r requirements.txt 
    ```
1. Add necessary folders to `PYTHONPATH` (below the bash example)
    ```shell
    export PYTHONPATH=${PYTHONPATH}:`echo ../.. ../{pyipv8,tribler-common,tribler-core} | tr " " :`
    ```
   
## Torrent seeding

To start torrents' seeding run the following script:

```bash
python3 seeder.py <source folder>
```

Consider the following folder structure:

```
source folder
├ sub_directory
| ├ file1
| └file2
├ sub_directory2
| ├ file3
| └ file4
├ thumbnail.png
└ description.md
```

In this particular example, `seeder.py` will create two torrents:
`sub_directory.torrent` and `sub_directory2.torrent`.

`seeder.py` will start to seed them through BitTorrent protocol after creating.

## Data disseminating

To start disseminating data through Tribler's network run the following script:

```bash
python3 disseminator.py <source folder>
```

This script will create a channel and will disseminate it to Tribler.

Consider the following folder structure:

```
source folder
├ sub_directory.torrent
├ sub_directory2.torrent
├ thumbnail.png
└ description.md
```

Above you can see two "special" files:
* thumbnail.png
* description.md

The channel will be created with description based on these files. 
As the channel name, the source folder's name will be used.

### Error reporting

In case you want errors to be reported, you can use [Sentry](https://develop.sentry.dev/)

To enable error reporting, specify the following environment variable:

```bash
export SENTRY_URL=<sentry_url>
```

URL can be taken directly from a corresponding Sentry project.

### Generate test data

The following script generates `1GB` dataset divided into `1024` folders:

```shell
python3 generate_test_data.py -d /tmp/test_data  
```