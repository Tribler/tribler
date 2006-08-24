from Tribler.Category.Category import *


if __name__ == "__main__":
    filesrc = "C:/Documents and Settings/yuan/Application Data/.Tribler/torrent2/0aa295564c738064a70b4b5a9e858be1daefda88.torrent"
    c = Category()
    print c.getCategories(filesrc)