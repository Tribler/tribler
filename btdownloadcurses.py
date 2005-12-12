#!/usr/bin/env python

# Written by Henry 'Pi' James
# see LICENSE.txt for license information

SPEW_SCROLL_RATE = 1

from BitTornado import PSYCO
if PSYCO.psyco:
    try:
        import psyco
        assert psyco.__version__ >= 0x010100f0
        psyco.full()
    except:
        pass

from BitTornado.download_bt1 import BT1Download, defaults, parse_params, get_usage, get_response
from BitTornado.RawServer import RawServer, UPnP_ERROR
from random import seed
from socket import error as socketerror
from BitTornado.bencode import bencode
from BitTornado.natpunch import UPnP_test
from threading import Event
from os.path import abspath
from signal import signal, SIGWINCH
from sha import sha
from sys import argv, exit
import sys
from time import time, strftime
from BitTornado.clock import clock
from BitTornado import createPeerID
from BitTornado.ConfigDir import ConfigDir

try:
    import curses
    import curses.panel
    from curses.wrapper import wrapper as curses_wrapper
    from signal import signal, SIGWINCH 
except:
    print 'Textmode GUI initialization failed, cannot proceed.'
    print
    print 'This download interface requires the standard Python module ' \
       '"curses", which is unfortunately not available for the native ' \
       'Windows port of Python. It is however available for the Cygwin ' \
       'port of Python, running on all Win32 systems (www.cygwin.com).'
    print
    print 'You may still use "btdownloadheadless.py" to download.'
    sys.exit(1)

assert sys.version >= '2', "Install Python 2.0 or greater"
try:
    True
except:
    True = 1
    False = 0

def fmttime(n):
    if n == 0:
        return 'download complete!'
    try:
        n = int(n)
        assert n >= 0 and n < 5184000  # 60 days
    except:
        return '<unknown>'
    m, s = divmod(n, 60)
    h, m = divmod(m, 60)
    return 'finishing in %d:%02d:%02d' % (h, m, s)

def fmtsize(n):
    s = str(n)
    size = s[-3:]
    while len(s) > 3:
        s = s[:-3]
        size = '%s,%s' % (s[-3:], size)
    if n > 999:
        unit = ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB', 'YiB']
        i = 1
        while i + 1 < len(unit) and (n >> 10) >= 999:
            i += 1
            n >>= 10
        n = float(n) / (1 << 10)
        size = '%s (%.0f %s)' % (size, n, unit[i])
    return size


class CursesDisplayer:
    def __init__(self, scrwin, errlist, doneflag):
        self.scrwin = scrwin
        self.errlist = errlist
        self.doneflag = doneflag
        
        signal(SIGWINCH, self.winch_handler)
        self.changeflag = Event()

        self.done = 0
        self.file = ''
        self.fileSize = ''
        self.activity = ''
        self.status = ''
        self.progress = ''
        self.downloadTo = ''
        self.downRate = '---'
        self.upRate = '---'
        self.shareRating = ''
        self.seedStatus = ''
        self.peerStatus = ''
        self.errors = []
        self.last_update_time = 0
        self.spew_scroll_time = 0
        self.spew_scroll_pos = 0

        self._remake_window()

    def winch_handler(self, signum, stackframe):
        self.changeflag.set()
        curses.endwin()
        self.scrwin.refresh()
        self.scrwin = curses.newwin(0, 0, 0, 0)
        self._remake_window()

    def _remake_window(self):
        self.scrh, self.scrw = self.scrwin.getmaxyx()
        self.scrpan = curses.panel.new_panel(self.scrwin)
        self.labelh, self.labelw, self.labely, self.labelx = 11, 9, 1, 2
        self.labelwin = curses.newwin(self.labelh, self.labelw,
                                      self.labely, self.labelx)
        self.labelpan = curses.panel.new_panel(self.labelwin)
        self.fieldh, self.fieldw, self.fieldy, self.fieldx = (
                            self.labelh, self.scrw-2 - self.labelw-3,
                            1, self.labelw+3)
        self.fieldwin = curses.newwin(self.fieldh, self.fieldw,
                                      self.fieldy, self.fieldx)
        self.fieldwin.nodelay(1)
        self.fieldpan = curses.panel.new_panel(self.fieldwin)
        self.spewh, self.speww, self.spewy, self.spewx = (
            self.scrh - self.labelh - 2, self.scrw - 3, 1 + self.labelh, 2)
        self.spewwin = curses.newwin(self.spewh, self.speww,
                                     self.spewy, self.spewx)
        self.spewpan = curses.panel.new_panel(self.spewwin)
        try:
            self.scrwin.border(ord('|'),ord('|'),ord('-'),ord('-'),ord(' '),ord(' '),ord(' '),ord(' '))
        except:
            pass
        self.labelwin.addstr(0, 0, 'file:')
        self.labelwin.addstr(1, 0, 'size:')
        self.labelwin.addstr(2, 0, 'dest:')
        self.labelwin.addstr(3, 0, 'progress:')
        self.labelwin.addstr(4, 0, 'status:')
        self.labelwin.addstr(5, 0, 'dl speed:')
        self.labelwin.addstr(6, 0, 'ul speed:')
        self.labelwin.addstr(7, 0, 'sharing:')
        self.labelwin.addstr(8, 0, 'seeds:')
        self.labelwin.addstr(9, 0, 'peers:')
        curses.panel.update_panels()
        curses.doupdate()
        self.changeflag.clear()


    def finished(self):
        self.done = 1
        self.activity = 'download succeeded!'
        self.downRate = '---'
        self.display(fractionDone = 1)

    def failed(self):
        self.done = 1
        self.activity = 'download failed!'
        self.downRate = '---'
        self.display()

    def error(self, errormsg):
        newerrmsg = strftime('[%H:%M:%S] ') + errormsg
        self.errors.append(newerrmsg)
        self.errlist.append(newerrmsg)
        self.display()

    def display(self, fractionDone = None, timeEst = None,
            downRate = None, upRate = None, activity = None,
            statistics = None, spew = None, **kws):

        inchar = self.fieldwin.getch()
        if inchar == 12: # ^L
            self._remake_window()
        elif inchar in (ord('q'),ord('Q')):
            self.doneflag.set()

        if activity is not None and not self.done:
            self.activity = activity
        elif timeEst is not None:
            self.activity = fmttime(timeEst)
        if self.changeflag.isSet():
            return
        if self.last_update_time + 0.1 > clock() and fractionDone not in (0.0, 1.0) and activity is not None:
            return
        self.last_update_time = clock()
        if fractionDone is not None:
            blocknum = int(self.fieldw * fractionDone)
            self.progress = blocknum * '#' + (self.fieldw - blocknum) * '_'
            self.status = '%s (%.1f%%)' % (self.activity, fractionDone * 100)
        else:
            self.status = self.activity
        if downRate is not None:
            self.downRate = '%.1f KB/s' % (float(downRate) / (1 << 10))
        if upRate is not None:
            self.upRate = '%.1f KB/s' % (float(upRate) / (1 << 10))
        if statistics is not None:
           if (statistics.shareRating < 0) or (statistics.shareRating > 100):
               self.shareRating = 'oo  (%.1f MB up / %.1f MB down)' % (float(statistics.upTotal) / (1<<20), float(statistics.downTotal) / (1<<20))
           else:
               self.shareRating = '%.3f  (%.1f MB up / %.1f MB down)' % (statistics.shareRating, float(statistics.upTotal) / (1<<20), float(statistics.downTotal) / (1<<20))
           if not self.done:
              self.seedStatus = '%d seen now, plus %.3f distributed copies' % (statistics.numSeeds,0.001*int(1000*statistics.numCopies2))
           else:
              self.seedStatus = '%d seen recently, plus %.3f distributed copies' % (statistics.numOldSeeds,0.001*int(1000*statistics.numCopies))
           self.peerStatus = '%d seen now, %.1f%% done at %.1f kB/s' % (statistics.numPeers,statistics.percentDone,float(statistics.torrentRate) / (1 << 10))

        self.fieldwin.erase()
        self.fieldwin.addnstr(0, 0, self.file, self.fieldw, curses.A_BOLD)
        self.fieldwin.addnstr(1, 0, self.fileSize, self.fieldw)
        self.fieldwin.addnstr(2, 0, self.downloadTo, self.fieldw)
        if self.progress:
            self.fieldwin.addnstr(3, 0, self.progress, self.fieldw, curses.A_BOLD)
        self.fieldwin.addnstr(4, 0, self.status, self.fieldw)
        self.fieldwin.addnstr(5, 0, self.downRate, self.fieldw)
        self.fieldwin.addnstr(6, 0, self.upRate, self.fieldw)
        self.fieldwin.addnstr(7, 0, self.shareRating, self.fieldw)
        self.fieldwin.addnstr(8, 0, self.seedStatus, self.fieldw)
        self.fieldwin.addnstr(9, 0, self.peerStatus, self.fieldw)

        self.spewwin.erase()

        if not spew:
            errsize = self.spewh
            if self.errors:
                self.spewwin.addnstr(0, 0, "error(s):", self.speww, curses.A_BOLD)
                errsize = len(self.errors)
                displaysize = min(errsize, self.spewh)
                displaytop = errsize - displaysize
                for i in range(displaysize):
                    self.spewwin.addnstr(i, self.labelw, self.errors[displaytop + i],
                                 self.speww-self.labelw-1, curses.A_BOLD)
        else:
            if self.errors:
                self.spewwin.addnstr(0, 0, "error:", self.speww, curses.A_BOLD)
                self.spewwin.addnstr(0, self.labelw, self.errors[-1],
                                 self.speww-self.labelw-1, curses.A_BOLD)
            self.spewwin.addnstr(2, 0, "  #     IP                 Upload           Download     Completed  Speed", self.speww, curses.A_BOLD)


            if self.spew_scroll_time + SPEW_SCROLL_RATE < clock():
                self.spew_scroll_time = clock()
                if len(spew) > self.spewh-5 or self.spew_scroll_pos > 0:
                    self.spew_scroll_pos += 1
            if self.spew_scroll_pos > len(spew):
                self.spew_scroll_pos = 0

            for i in range(len(spew)):
                spew[i]['lineno'] = i+1
            spew.append({'lineno': None})
            spew = spew[self.spew_scroll_pos:] + spew[:self.spew_scroll_pos]                
            
            for i in range(min(self.spewh - 5, len(spew))):
                if not spew[i]['lineno']:
                    continue
                self.spewwin.addnstr(i+3, 0, '%3d' % spew[i]['lineno'], 3)
                self.spewwin.addnstr(i+3, 4, spew[i]['ip'], 15)
                if spew[i]['uprate'] > 100:
                    self.spewwin.addnstr(i+3, 20, '%6.0f KB/s' % (float(spew[i]['uprate']) / 1000), 11)
                self.spewwin.addnstr(i+3, 32, '-----', 5)
                if spew[i]['uinterested'] == 1:
                    self.spewwin.addnstr(i+3, 33, 'I', 1)
                if spew[i]['uchoked'] == 1:
                    self.spewwin.addnstr(i+3, 35, 'C', 1)
                if spew[i]['downrate'] > 100:
                    self.spewwin.addnstr(i+3, 38, '%6.0f KB/s' % (float(spew[i]['downrate']) / 1000), 11)
                self.spewwin.addnstr(i+3, 50, '-------', 7)
                if spew[i]['dinterested'] == 1:
                    self.spewwin.addnstr(i+3, 51, 'I', 1)
                if spew[i]['dchoked'] == 1:
                    self.spewwin.addnstr(i+3, 53, 'C', 1)
                if spew[i]['snubbed'] == 1:
                    self.spewwin.addnstr(i+3, 55, 'S', 1)
                self.spewwin.addnstr(i+3, 58, '%5.1f%%' % (float(int(spew[i]['completed']*1000))/10), 6)
                if spew[i]['speed'] is not None:
                    self.spewwin.addnstr(i+3, 64, '%5.0f KB/s' % (float(spew[i]['speed'])/1000), 10)

            if statistics is not None:
                self.spewwin.addnstr(self.spewh-1, 0,
                        'downloading %d pieces, have %d fragments, %d of %d pieces completed'
                        % ( statistics.storage_active, statistics.storage_dirty,
                            statistics.storage_numcomplete,
                            statistics.storage_totalpieces ), self.speww-1 )

        curses.panel.update_panels()
        curses.doupdate()

    def chooseFile(self, default, size, saveas, dir):
        self.file = default
        self.fileSize = fmtsize(size)
        if saveas == '':
            saveas = default
        self.downloadTo = abspath(saveas)
        return saveas

def run(scrwin, errlist, params):
    doneflag = Event()
    d = CursesDisplayer(scrwin, errlist, doneflag)
    try:
        while 1:
            configdir = ConfigDir('downloadcurses')
            defaultsToIgnore = ['responsefile', 'url', 'priority']
            configdir.setDefaults(defaults,defaultsToIgnore)
            configdefaults = configdir.loadConfig()
            defaults.append(('save_options',0,
             "whether to save the current options as the new default configuration " +
             "(only for btdownloadcurses.py)"))
            try:
                config = parse_params(params, configdefaults)
            except ValueError, e:
                d.error('error: ' + str(e) + '\nrun with no args for parameter explanations')
                break
            if not config:
                d.error(get_usage(defaults, d.fieldw, configdefaults))
                break
            if config['save_options']:
                configdir.saveConfig(config)
            configdir.deleteOldCacheData(config['expire_cache_data'])

            myid = createPeerID()
            seed(myid)

            rawserver = RawServer(doneflag, config['timeout_check_interval'],
                                  config['timeout'], ipv6_enable = config['ipv6_enabled'],
                                  failfunc = d.failed, errorfunc = d.error)

            upnp_type = UPnP_test(config['upnp_nat_access'])
            while True:
                try:
                    listen_port = rawserver.find_and_bind(config['minport'], config['maxport'],
                                    config['bind'], ipv6_socket_style = config['ipv6_binds_v4'],
                                    upnp = upnp_type, randomizer = config['random_port'])
                    break
                except socketerror, e:
                    if upnp_type and e == UPnP_ERROR:
                        d.error('WARNING: COULD NOT FORWARD VIA UPnP')
                        upnp_type = 0
                        continue
                    d.error("Couldn't listen - " + str(e))
                    d.failed()
                    return

            response = get_response(config['responsefile'], config['url'], d.error)
            if not response:
                break

            infohash = sha(bencode(response['info'])).digest()
            
            dow = BT1Download(d.display, d.finished, d.error, d.error, doneflag,
                            config, response, infohash, myid, rawserver, listen_port,
                            configdir)
            
            if not dow.saveAs(d.chooseFile):
                break

            if not dow.initFiles(old_style = True):
                break
            if not dow.startEngine():
                dow.shutdown()
                break
            dow.startRerequester()
            dow.autoStats()

            if not dow.am_I_finished():
                d.display(activity = 'connecting to peers')
            rawserver.listen_forever(dow.getPortHandler())
            d.display(activity = 'shutting down')
            dow.shutdown()
            break

    except KeyboardInterrupt:
        # ^C to exit.. 
        pass 
    try:
        rawserver.shutdown()
    except:
        pass
    if not d.done:
        d.failed()


if __name__ == '__main__':
    if argv[1:] == ['--version']:
        print version
        exit(0)
    if len(argv) <= 1:
        print "Usage: btdownloadcurses.py <global options>\n"
        print get_usage(defaults)
        exit(1)

    errlist = []
    curses_wrapper(run, errlist, argv[1:])

    if errlist:
       print "These errors occurred during execution:"
       for error in errlist:
          print error