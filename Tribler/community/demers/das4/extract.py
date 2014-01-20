import sys
import logging

logger = logging.getLogger(__name__)

f = open("sum_total_records.txt")
f2 = open("received_records_10.txt", 'w')
f2.write("#nrpeers, took, partnr")

piece_created = {}

peer_received = {}
piece_received = {}
took_list = []

for line in f:
    if line[0] == '#':
        continue

    parts = line.split()
    if not parts[0].isdigit():
        continue

    time = int(parts[0])
    peers = [int(float(part)) for part in parts[1:]]
    created = max(peers)
    if created not in piece_created:
        piece_created[created] = time
        # piece_created[created] = 120 * created
        logger.info("new part %s %s %s %s", peers.index(created), time, created * 120, piece_received.get(created - 1, 0))

    updated_parts = set()

    for peer, part in enumerate(peers):
        peer += 1

        if peer_received.get(peer, 0) != part:
            peer_received[peer] = part
            piece_received[part] = piece_received.get(part, 0) + 1

            took = time - piece_created[part]

            f2.write("%s %s %s" % piece_received[part], took, part)
            if piece_received[part] == 1000:
                took_list.append(took)
                logger.info("received part %s %s %s", part, took, sum(took_list) / float(len(took_list)))

f.close()
f2.close()
