import sys

f = open("sum_total_records.txt")
f2 = open("received_records_10.txt", 'w')
print >> f2, "#nrpeers, took, partnr"

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
        #piece_created[created] = 120 * created
        print "new part", peers.index(created), time, created * 120, piece_received.get(created-1, 0)

    updated_parts = set()
    
    for peer, part in enumerate(peers):
        peer += 1
        
        if peer_received.get(peer, 0) != part:
            peer_received[peer] = part
            piece_received[part] = piece_received.get(part, 0) + 1
            
            took = time - piece_created[part]
    
            print >> f2, piece_received[part], took, part
            if piece_received[part] == 1000:
                took_list.append(took)
                print "received part", part, took, sum(took_list)/float(len(took_list))
                        
f.close()
f2.close()
