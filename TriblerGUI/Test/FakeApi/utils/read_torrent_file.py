str = ""

with open("data/random_torrents.dat") as random_torrent_files:
    content = random_torrent_files.readlines()
    for random_torrent in content:
        torrent_parts = random_torrent.split("\t")
        print torrent_parts[0]
        str = str + torrent_parts[0] + ", "

print str
