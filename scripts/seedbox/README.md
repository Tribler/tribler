# Seedbox

This folder contains scripts for effortlessly setting up a seedbox.

## Prerequisites

Clone the tribler repo:

 ```bash
 git clone https://github.com/Tribler/tribler.git
 ```

Install requirements:

 ```bash
 python3 -m pip install -r scripts/seeedbox/requirements.txt 
 ```

## Torrent seeding

To start torrents' seeding run the following script:

```bash
python3 seeder.py <source folder>
```

Consider the following folder structure:

```text
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

### Error reporting

In case you want errors to be reported, you can use [Sentry](https://develop.sentry.dev/)

To enable error reporting, specify the following environment variable:

```bash
export SENTRY_URL=<sentry_url>
```

URL can be taken directly from a corresponding Sentry project.
