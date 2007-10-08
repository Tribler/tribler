#import threading
import math
import time
from observer import *
from canvasobjects import CanvasObjects
import wx

minr, maxr = 4, 40

cx,  cy = 300, 300 # inner system central position
rs = 140
degrees = 3.14159265358979/180


def getsize(files):
    # return 30, 0
    size, bold = math.sqrt(files), 0
    if size < minr: size = minr
    if size > maxr: size, bold = maxr, 1
    return size, bold

def polar(r, a):
    return cx + r * math.cos(a * degrees), cy + r * math.sin(a * degrees)

def MakeLine(origin, dest, fill='black', width=1, factor = 1):
    if Line.lines.has_key((origin, dest)):
        return Line.lines[(origin, dest)]
    if Line.lines.has_key((dest, origin)):
        return Line.lines[(dest, origin)]
        
    line = Line(origin, dest, fill, width, factor)
    return line

def DeleteLine(origin, dest):
    if Line.lines.has_key((origin, dest)):
        Line.lines[(origin, dest)].delete()
    if Line.lines.has_key((dest, origin)):
        Line.lines[(dest, origin)].delete()
        
def LineExists(origin, dest):
    if Line.lines.has_key((origin, dest)) or\
       Line.lines.has_key((dest, origin)):
        return True
    return False


class Line(Observer):
    lines = {}

    def __init__(self, origin, dest, fill='black', width=1, factor = 1):
        self.origin, self.dest = origin, dest
        
        self.x1 = origin.x
        self.y1 = origin.y
        self.x2 = origin.x + (dest.x - origin.x) * factor
        self.y2 = origin.y + (dest.y - origin.y) * factor
        
        self.factor = factor
        
        self.line = CanvasObjects.createLine( origin.canvas, \
            {'x1':self.x1, 'y1':self.y1, 'x2':self.x2, 'y2':self.y2, 'fill':fill, 'width':width})
        
        # self.line = Canvas.Line(origin.canvas,
        #                        origin.x, origin.y, dest.x, dest.y,
        #                        fill=fill, width=width)
        # should create a canvas line object to draw on dc?
        self.fill = fill
        self.width = width
        self.line.lower() # puts this line below the others, that means it is one of the first to be drawn
        self.subscribe(origin, moved=self.update, deleted=self.delete)
        self.subscribe(dest, moved=self.update, deleted=self.delete)
        Line.lines[(origin, dest)] = Line.lines[(dest, origin)] = self

    def config(self, *args, **kw):
        apply(self.line.config, args, kw)

    def update(self, *args):
        self.line.coords([(self.origin.x, self.origin.y),
                          (self.origin.x + (self.dest.x - self.origin.x)*self.factor, \
                           self.origin.y + (self.dest.y - self.origin.y)*self.factor)])

    def delete(self, *args):
        Observer.delete(self)
        self.line.delete()
        try: del Line.lines[(self.origin, self.dest)]
        except KeyError: pass
        try: del Line.lines[(self.dest, self.origin)]
        except KeyError: pass

class Host(Notifier):
    ovaltohost = {}
    (QUEUED, CONNECTING, REFUSED, CONNECTED, DROPPED) = range(5)
    colours = {QUEUED:     ('black', ''),
               CONNECTING: ('black', 'light blue'),
               REFUSED:    ('grey', 'light blue'),
               CONNECTED:  ('black', 'yellow'),
               DROPPED:    ('grey', 'light blue')}
    colours = {QUEUED:     ('black', 'white'),
               CONNECTING: ('black', 'light blue'),
               REFUSED:    ('black', 'green'),
               CONNECTED:  ('black', 'yellow'),
               DROPPED:    ('grey', 'dark grey')}
    DIRECT_LINE = 'grey'
    INDIRECT_LINE = '#a0d0a0'

    def __init__(self, canvas, addr, files, parent=None, conn=None, bartervalue = 1):
        # conn will be the permid
        self.canvas, self.addr, self.files, self.parent, self.conn = \
            canvas, addr, files, parent, conn
        self.children = []
        self.neighbours = {}
        self.error = None
        self.counts = {}

        self.size, self.bold = getsize(files)
        self.oval = self.branch = self.query = self.text = None
        self.radius, self.amin, self.amax = \
            parent and self.parent.insert(self) or (0.0, 0.0, 360.0)

        self.x, self.y = self.xy()
        self.oval = CanvasObjects.createOval(canvas, 0, 0, 0, 0)
        Host.ovaltohost[self.oval] = self
        self.branch = None
        self.text = None

        if self.parent:
            self.branch = MakeLine(self, self.parent, Host.DIRECT_LINE, width = 1.0 + float(bartervalue) / 100000)
        
        self.text = CanvasObjects.createText(canvas, self.x, self.y, font=('helvetica', 8), justify='center', text='') # addr)
        # self.text = Canvas.CanvasText(
        #    canvas, self.x, self.y, font=('helvetica', 8), justify='center')
        self.query = CanvasObjects.createText(canvas, self.x, self.y, font=('helvetica', 8), justify='left', anchor='s', text='')
        # self.query = Canvas.CanvasText(
        #    canvas, self.x, self.y,
        #    font=('helvetica', 8), justify='left', anchor='s', text='')
        self.resize(files)
        self.setstate(Host.QUEUED)
        # should call a repaint event?
        # self.canvas.update()
        # time.sleep(TF*0.05)

    def __repr__(self):
        return '<Host for %s>' % repr(self.conn)

    def __hash__(self): return id(self)

    def init(self, conn):
        self.conn = conn
        self.setstate(Host.CONNECTING)

    def count(self, kind):
        self.lastactivity = time.time()
        self.counts[kind] = self.counts.get(kind, 0) + 1

    def config(self, *args, **kw):
        apply(self.oval.config, args, kw)

    def join(self, host):
        if self is host: return
        MakeLine(self, host, Host.INDIRECT_LINE)
        self.neighbours[host] = 1
        host.neighbours[self] = 1

    def split(self, host):
        DeleteLine(self, host)
        if self.neighbours.has_key(host): del self.neighbours[host]
        if host.neighbours.has_key(self): del host.neighbours[self]

    def setstate(self, state):
        self.state = state
        circle, disc = Host.colours[state]
        self.oval.config(outline=circle, fill=disc)

    def flash(self, colour, duration=500):
        pass
        # changes the color of the oval representing the host for 500 ms
        self.oval.config(fill=colour)
        self.canvas.refresh()
        time.sleep(duration*TF)
        # self.canvas.tk.createtimerhandler(
        #    duration*TF, lambda s=self: s.setstate(s.state))
        self.setstate(self.state)

    def resize(self, files):
        self.files = files
        self.size, self.bold = getsize(files)
        #disable text for the moment !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
##        if self.size >= 20:
##            self.text.config(text='%s\n%s files' % (self.addr, self.files))
##        elif self.size >= 5:
##            self.text.config(text='%s' % self.files)
        self.query.coords([(self.x, self.y - self.size)])
        self.oval.config(width=self.bold and 3 or 1)
        self.oval.coords([(self.x - self.size, self.y - self.size),
                          (self.x + self.size, self.y + self.size)])
        if self.parent:
            self.parent.arrange()

    def xy(self, radius=None, angle=None):
        self.angle = (self.amin + self.amax) / 2.0
        return polar(radius or self.radius, angle or self.angle)

    def movexy(self, x, y):
        if self.oval:
            self.oval.coords([(x - self.size, y - self.size),
                              (x + self.size, y + self.size)])
        if self.text:
            self.text.coords([(x, y)])
        if self.query:
            self.query.coords([(x, y - self.size)])
        self.x, self.y = x, y

    def move(self, radius, amin, amax):
        self.radius, self.amin, self.amax = radius, amin, amax
        self.x, self.y = self.xy()
        self.movexy(self.x, self.y)
        self.send('moved')
        self.arrange()

    def delete(self):
        Notifier.delete(self)
        self.oval.delete()
        del Host.ovaltohost[self.oval]
        if self.text: self.text.delete()
        if self.query: self.query.delete()
        if self.parent: self.parent.remove(self)

    def totalsize(self):
        if hasattr(self, 'calctotal'): raise RuntimeError, self
        self.calctotal = 1
        total = 0.0
        for child in self.children:
            total = total + child.totalsize()
        del self.calctotal
        return total + self.size

    def gotquery(self, key):
        self.query.config(text=key[:30])
        self.canvas.update()
        time.sleep(TF*0.05)
        #self.canvas.tk.createtimerhandler(
        #    2000*TF, lambda c=self.query.config: c(text=''))
        self.query.config( text='')

    def arrange(self, skip=None):

        result = None
        if self.children:
            total = self.totalsize() - self.size
            wedge = self.amax - self.amin
            amin = self.amin
            for child in self.children:
                amax = amin + wedge * (child.totalsize()/total)
                if child is skip:
                    result = (self.radius + rs, amin, amax)
                else:
                    child.move(self.radius + rs, amin, amax)
                amin = amax
        return result

    def insert(self, child):
        self.children.append(child)
        if self.parent:
            return self.parent.radius + rs, 0, 0
            radius, amin, amax = self.parent.arrange(skip=self)
            self.move(radius, amin, amax)
        return self.arrange(skip=child)

    def remove(self, child):
        self.children.remove(child)
        if self.parent:
            radius, amin, amax = self.parent.arrange(skip=self)
            self.move(radius, amin, amax)
        self.arrange()

    def connect(self):
        self.setstate(Host.CONNECTED)

    def refuse(self):
        self.setstate(Host.REFUSED)

    def drop(self):
        self.setstate(Host.DROPPED)

