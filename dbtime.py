import sys

if len(sys.argv) > 1:
    f = open(sys.argv[1])
else:
    f = open('db_execute.txt')
i = 0
prev_ts = {}
prev_line = {}
prev_sql = {}
prev_op = {}
mem = []
first_ts = 0
commits = []
for line in f:
    i += 1
    if 'sqldb:' in line:
        terms = line.split()
        try:
            ts = float(terms[0])
        except:
            break
        flag = terms[2]
        #print terms
        cur_id = terms[3]
        #if 'insert ' in line.lower():
        #    print i, line
        if 'thread' not in cur_id.lower():
            #print cur_id, i
            continue
        if flag == 'execute' or flag == 'executemany':
            
            if cur_id not in prev_ts:
                prev_ts[cur_id] = 0
                prev_line[cur_id] = 0
                prev_sql[cur_id] = 0
                prev_op[cur_id] = 0

            #assert prev_ts[cur_id] == 0, (cur_id, i, prev_ts[cur_id])

            prev_ts[cur_id] = ts
            prev_line[cur_id] = i
            prev_sql[cur_id] = line
            prev_op[cur_id] = terms[5]

            if first_ts == 0:
                first_ts = ts
            
            
            #if op == 'write':
            #    pass
        elif flag == 'done':
            #assert prev_ts[cur_id] != 0, (cur_id, i, prev_ts[cur_id])
            if prev_ts[cur_id] == 0:
                continue
            cost = ts - prev_ts[cur_id]
            mem.append((cost, prev_line[cur_id], ts, prev_sql[cur_id], cur_id))
            if cost > 0.3:
                print 'execut time:->', cost, prev_line[cur_id], ts, '[[', prev_sql[cur_id][10:190]
            #prev_ts[cur_id] = ts
            prev_ts[cur_id] = 0
        elif flag == 'start_commit':
            #assert prev_ts[cur_id] == 0, (cur_id, i, prev_ts[cur_id])
            prev_ts[cur_id] = ts
        elif flag == 'commit':
            if prev_ts[cur_id] == 0:
                continue
            assert prev_ts[cur_id] != 0, (cur_id, i, prev_ts[cur_id])
            if prev_op[cur_id] == 'write':
                commits.append((prev_op[cur_id], ts - prev_ts[cur_id], prev_line[cur_id], i, cur_id, prev_sql[cur_id][50:150]))
                if ts - prev_ts[cur_id] > 0.3:
                    print 'commit time:<-', ts - prev_ts[cur_id], prev_line[cur_id], '[[', prev_sql[cur_id][10:110], len(commits), ']]'
            prev_ts[cur_id] = 0
mem.sort()
mem.reverse()
i = 0   
for m in mem:
    if m[4] == 'MainThread':
        print 'top execute time:', m[0], m[1], m[2]-first_ts, m[2], '||', m[3][50:130]
        i += 1
        if i > 20:
            break

#commits = filter(lambda x:x[5]

commits.sort()
commits.reverse()
for m in commits[:10]:
    print 'top commit time:', m
