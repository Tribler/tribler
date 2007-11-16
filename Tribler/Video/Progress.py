# Written by Arno Bakker, Jan David Mol
# see LICENSE.txt for license information

import wx
import sys


class BufferInfo:
    """ Arno: WARNING: the self.tricolore member is read by the MainThread and 
        written by the network thread. As it is a fixed array with simple values, this
        concurrency problem is ignored.
    """
    NOFILL = " "
    SOMEFILL = ".-+="
    ALLFILL = "#"

    def __init__(self,numbuckets=100,full=False):
        self.numbuckets = numbuckets
        self.playable = False
        self.movieselector = None
        if full == True:
            self.tricolore = [2] * self.numbuckets
    
    def set_numpieces(self,numpieces):
        self.numpieces = numpieces
        self.buckets = [0] * self.numbuckets
        self.tricolore = [0] * self.numbuckets
        #self.bucketsize = int(ceil(float(self.numpieces) / self.numbuckets))
        self.bucketsize = float(self.numpieces) / float(self.numbuckets)
        self.lastbucketsize = self.numpieces - int(float(self.numbuckets-1) * self.bucketsize)

    def complete( self, piece ):
        bucket = int(float(piece) / self.bucketsize)
        
        #print >>sys.stderr,"BUCKET",bucket,"piece",piece,"bucksize",self.bucketsize
        # If there is a multi-file torrent that has been partially downloaded before we go
        # to VOD, it can happen that pieces outside the range of the file selected are
        # reported as complete here.
        if bucket < 0 or bucket >= self.numbuckets:
            return
        
        self.buckets[bucket] += 1

        fill = self.buckets[bucket]
        if bucket == self.numbuckets-1:
            total = self.lastbucketsize
        else:
            total = int(self.bucketsize)
            
        if fill == 0:
            colour = 0
        elif fill >= total:
            colour = 2
        else:
            colour = 1

        self.tricolore[bucket] = colour

    def str( self ):
        def chr( fill, total ):
            if fill == 0:
                return self.NOFILL
            if fill >= int(total):
                return self.ALLFILL

            index = int(float(fill*len(self.SOMEFILL))/total)
            if index >= len(self.SOMEFILL):
                index = len(self.SOMEFILL)-1
            return self.SOMEFILL[index]

        chars = [chr( self.buckets[i], self.bucketsize ) for i in xrange(0,self.numbuckets-1)]
        chars.append( chr( self.buckets[-1], self.lastbucketsize ) )
        return "".join(chars)


    def set_playable(self):
        self.playable = True
        
    def get_playable(self):
        return self.playable

    def set_movieselector(self,movieselector):
        self.movieselector = movieselector
    
    def get_bitrate(self):
        if self.movieselector is not None:
            return self.movieselector.get_bitrate()
        else:
            return 0.0

    def get_blocks(self):
        return self.tricolore


class ProgressInf:
    def __init__(self):
        self.bufferinfo = BufferInfo()
        self.callback = None
        
    def get_bufferinfo(self):
        return self.bufferinfo

    def set_callback(self,callback):
        self.callback = callback
        
    def bufferinfo_updated_callback(self):
        if self.callback is not None:
            self.callback()
        


class ProgressBar(wx.Control):
    #def __init__(self, parent, colours = ["#cfcfcf","#d7ffd7","#00ff00"], *args, **kwargs ):
    #def __init__(self, parent, colours = ["#cfcfcf","#fde72d","#00ff00"], *args, **kwargs ):
    #def __init__(self, parent, colours = ["#ffffff","#fde72d","#00ff00"], *args, **kwargs ):
    def __init__(self, parent, colours = ["#ffffff","#CBCBCB","#ff3300"], *args, **kwargs ):
        self.colours = colours
        self.pens    = [wx.Pen(c,0) for c in self.colours]
        self.brushes = [wx.Brush(c) for c in self.colours]
        self.reset()

        style = wx.SIMPLE_BORDER
        wx.Control.__init__(self, parent, -1, style=style)
        self.SetMaxSize((-1,6))
        self.SetMinSize((1,6))
        self.SetBackgroundColour(wx.WHITE)

        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)
        self.SetSize((100,6))

        self.progressinf = None

    def AcceptsFocus(self):
        return False

    def OnEraseBackground(self, event):
        pass # Or None
    
    def OnPaint(self, evt):
        
        # define condition
        x,y,maxw,maxh = self.GetClientRect()
        #dc.DrawRectangle(x,y,)
        
        arrowsize = 6
        arrowspace = 1
        numrect = len(self.blocks)

        # create blocks
        w = max(1,maxw/numrect)
        h = maxh
        
        width, height = self.GetClientSizeTuple()
        buffer = wx.EmptyBitmap(width, height)
        #dc = wx.PaintDC(self)
        dc = wx.BufferedPaintDC(self, buffer)
        dc.BeginDrawing()
        dc.Clear()
        
        rectangles = [(x+i*w,y,w,h) for i in xrange(0,numrect)]

        # draw the blocks
        pens = [self.pens[c] for c in self.blocks]
        brushes = [self.brushes[c] for c in self.blocks]
                
        dc.DrawRectangleList(rectangles,pens,brushes)

        dc.EndDrawing()

    def set_blocks(self,blocks):
        """ Called by MainThread """
        self.blocks = blocks
        
    def setNormalPercentage(self, perc):
        perc = int(perc)
        self.blocks = ([2]*perc)+([0]* (100-perc))

    def reset(self,colour=0):
        self.blocks = [colour] * 100
        