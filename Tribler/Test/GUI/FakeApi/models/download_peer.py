from random import randint, uniform


class DownloadPeer:

    def __init__(self):
        self.ip = "%d.%d.%d.%d" % (randint(0, 255), randint(0, 255), randint(0, 255), randint(0, 255))
        self.port = randint(1000, 65536)
        self.id = "abcd"
        self.client = "Tribler x.x"
        self.connection_type = randint(0, 3)
        self.direction = "L" if randint(0, 1) == 0 else "R"
        self.completed = uniform(0, 1)
        self.downrate = randint(0, 10000)
        self.uprate = randint(0, 10000)

    def get_info_dict(self):
        return {
            "ip": self.ip,
            "port": self.port,
            "id": self.id,
            "extended_version": self.client,
            "connection_type": self.connection_type,
            "optimistic": True,
            "uinterested": True,
            "uchoked": True,
            "uhasqueries": True,
            "uflushed": True,
            "ueligable": True,
            "dinterested": True,
            "dchoked": True,
            "snubbed": True,
            "direction": self.direction,
            "completed": self.completed,
            "downrate": self.downrate,
            "uprate": self.uprate
        }
