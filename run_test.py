import subprocess

from Tribler.community.anontunnel.TunnelCommander import TunnelCommander

# retrieve stats
UDP_IP = "127.0.0.1"
UDP_PORT = 1081

# start tunnel
subprocess.Popen(["python2.7", "Tribler/community/anontunnel/Main.py", "-cmd " + str(UDP_PORT)])

# start swift
swift_leecher = subprocess.Popen(["./swift --proxy 127.0.0.1:1080 -h hash_here -t tracker:port -p"], subprocess.PIPE)
swift_leecher.wait()


# collect stats when download finishes
def on_stats(event, stats):
    print stats
    tc.stop()


tc = TunnelCommander((UDP_IP, UDP_PORT))
tc.subscribe("on_stats_response", on_stats)

tc.start()
tc.request_stats()
tc.join()