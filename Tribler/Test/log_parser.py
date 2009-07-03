import sys
import os

def parse_log_line(line, line_num):
    terms = line.split()
    try:
        timestamp = float(terms[0])
        key = terms[1]
        data = {'time':timestamp}
    except KeyboardInterrupt:
        raise KeyboardInterrupt
    except:
        return None
    
    if key == 'BUCA_STA':
        data['nRound'] = int(terms[2])
        data['nPeer'] = int(terms[3])
        data['nPref'] = int(terms[4]) 
        data['nConnCandidates'] = int(terms[5])
        data['nBlockSendList'] = int(terms[6])
        data['nBlockRecvList'] = int(terms[7])
        data['nConnectionsInSecureOver'] = int(terms[8])
        data['nConnectionsInBuddyCast'] = int(terms[9])
        data['nTasteConnectionList'] = int(terms[10])
        data['nRandomConnectionList'] = int(terms[11])
        data['nUnconnectableConnectionList'] = int(terms[12])

    elif key == 'CONN_TRY' or key == 'CONN_ADD' or key == 'CONN_DEL':
        try:
            data['ip'] = terms[2]
            data['port'] = int(terms[3])
            data['permid'] = terms[4]
            if key == 'CONN_ADD' or key == 'RECV_MSG' or key == 'SEND_MSG':
                data['oversion'] = terms[5]
        except KeyboardInterrupt:
            raise KeyboardInterrupt
        except Exception, msg:
            print >> sys.stderr, "Error in parse the log on line %d:"%line_num, Exception, msg
            return None
            
    elif key == 'RECV_MSG' or key == 'SEND_MSG':
        try:
            data['ip'] = terms[2]
            data['port'] = int(terms[3])
            data['permid'] = terms[4]
            data['oversion'] = terms[5]
            data['MSG_ID'] = terms[6]
            msg = ' '.join(terms[7:])
            data['msg'] = eval(msg)
            if key == 'RECV_MSG':
                data['msg']['permid'] = data['permid']
                data['msg']['ip']  = data['ip']
                data['msg']['port'] = data['port'] 
        except KeyboardInterrupt:
            raise KeyboardInterrupt
        except Exception, msg:
            print >> sys.stderr, "Error in eval the msg on line %d:"%line_num, Exception, msg
            return None
    
    elif key == 'RECV_QRY':
        try:
            data['permid'] = terms[2]
            data['oversion'] = int(terms[3])
            data['nqueries'] = int(terms[4])
            msg = ' '.join(terms[5:])
            data['msg'] = eval(msg)
            data['query'] = data['msg']['q'][7:]
        except KeyboardInterrupt:
            raise KeyboardInterrupt
        except Exception, msg:
            print >> sys.stderr, "Error in eval the msg on line %d:"%line_num, Exception, msg
            return None
        
    elif key == 'RPLY_QRY':
        pass
    
    if len(data) == 1:
        return None
    
    return key, data

def parse_log_file(file_path):
    file = open(file_path)
    i = 0
    for line in file:
        i += 1
        line = line.strip()
        if not line.startswith('#'):
            yield parse_log_line(line, i)
    file.close()
    
def parse_log_file_readall(file_path, N_BREAK):
    file = open(file_path)
    i = 0
    alldata = []
    for line in file:
        if N_BREAK > 0 and i >= N_BREAK:
            break
        i += 1
        line = line.strip()
        if not line.startswith('#'):
            res = parse_log_line(line, i)
            alldata.append(res)
    return alldata

def yield_files2load(file_paths):
    for file_path in file_paths:
        if os.path.isdir(file_path):
            files_in_dir = os.listdir(file_path)
            files2load = [os.path.join(file_path, afile) for afile in files_in_dir]
        else:
            files2load = [file_path]
        for afile in files2load:
            if afile.endswith('.log'):
                yield afile


def get_buddycast_data(file_path):
    file = open(file_path)
    i = 0
    for line in file:
        i += 1
        line = line.strip()
        if not line.startswith('#'):
            ret = parse_log_line(line, i)
            if ret is not None:
                key, data = ret
                if key == 'RECV_MSG':
                    yield data['permid'], int(data['oversion']), data['msg']
    file.close()

        

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print >> sys.stderr, "Must specify the path or directory of logs"
        sys.exit(1)
    
    i = 1
    for file_path in yield_files2load(sys.argv[1:]):
        print >> sys.stderr, "load", i, file_path
        i += 1
        #for ret in parse_log_file(file_path):
        for ret in get_buddycast_data(file_path):
            print "GOT",`ret`
