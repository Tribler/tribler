# Written by Arno Bakker, Jan David Mol
# see LICENSE.txt for license information

import wx,time
import sys,os


from Tribler.__init__ import LIBRARYNAME

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
        


class ProgressBar(wx.Panel):
    
    def __init__(self, parent, colours = ["#ffffff", "#92cddf", "#006dc0"], size = wx.DefaultSize):
        wx.Panel.__init__(self, parent, size = size, style = wx.NO_BORDER)
        self.pens = [wx.Pen(c) for c in colours]
        self.brushes = [wx.Brush(c) for c in colours]
        
        for i in xrange(len(self.pens)):
            if self.pens[i].GetColour() == wx.WHITE:
                self.pens[i] = None
        self.reset()
        
        self.SetMaxSize((-1,6))
        self.SetMinSize((1,6))
        self.SetBackgroundColour(wx.WHITE)

        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)
        
        self.completed = False

    def OnEraseBackground(self, event):
        pass # Or None
    
    def OnPaint(self, evt):
        dc = wx.BufferedPaintDC(self)
        dc.SetBackground(wx.Brush(self.GetBackgroundColour()))
        dc.Clear()
        
        x, y, maxw, maxh = self.GetClientRect()
        
        if len(self.blocks) > 0 and not self.completed:
            numrect = float(len(self.blocks))
            w = max(1, maxw / numrect)
        
            lines = [(x+i, y, x+i, maxh) for i in xrange(maxw) if self.blocks[int(i/w)]]
            pens = [self.pens[self.blocks[int(i/w)]] for i in xrange(maxw) if self.blocks[int(i/w)]]
            dc.DrawLineList(lines,pens)
        
        if self.completed:
            dc.SetBrush(self.brushes[2])
        else:
            dc.SetBrush(wx.TRANSPARENT_BRUSH)
        dc.SetPen(wx.BLACK_PEN)
        dc.DrawRectangle(x, y, maxw, maxh)

    def set_pieces(self, blocks):
        maxBlocks = max(self.GetClientRect().width, 100)
        haveBlocks = len(blocks)
        if haveBlocks > maxBlocks: #we need to group the blocks
            nrBlocksPerPixel = haveBlocks/maxBlocks
            
            sblocks = [0]*haveBlocks
            for i in xrange(maxBlocks):
                any = False
                all = True
                
                for j in xrange(nrBlocksPerPixel * i, nrBlocksPerPixel * (i+1)):
                    if blocks[j]:
                        any = True
                    else:
                        all = False
                        if any:
                            break
                if all:
                    sblocks[i] = 2
                elif any:
                    sblocks[i] = 1
            self.set_blocks(sblocks)
        
    def set_blocks(self,blocks):
        self.completed = all([x == 2 for x in blocks])
        self.blocks = blocks
        
    def setNormalPercentage(self, perc):
        maxBlocks = max(self.GetClientRect().width, 100)
        
        sblocks = [2] * int(perc * maxBlocks)
        sblocks += [0] * (maxBlocks-len(sblocks))
        self.set_blocks(sblocks)

    def reset(self,colour=0):
        sblocks = [colour] * 100
        self.set_blocks(sblocks)
        
class ProgressSlider(wx.Panel):
    
    def __init__(self, parent, utility, colours = ["#ffffff","#CBCBCB","#ff3300"], imgprefix= '', *args, **kwargs ):
        
        self.colours = colours
        #self.backgroundImage = wx.Image('')
        self.progress      = 0.0
        self.videobuffer  = 0.0
        self.videoPosition = 0
        self.timeposition = None
        self.videoLength   = None
        #wx.Control.__init__(self, parent, -1)
        wx.Panel.__init__(self, parent, -1)
        
        self.SetMaxSize((-1,25))
        self.SetMinSize((1,25))
        self.SetBackgroundColour(wx.WHITE)
        self.utility = utility
        self.bgImage = wx.Bitmap(os.path.join(self.utility.getPath(), LIBRARYNAME,'Video','Images',imgprefix+'background.png')) ## LIBRARYNAME
        self.dotImage = wx.Bitmap(os.path.join(self.utility.getPath(), LIBRARYNAME,'Video','Images',imgprefix+'sliderDot.png')) ## LIBRARYNAME
        self.dotImage_dis = wx.Bitmap(os.path.join(self.utility.getPath(), LIBRARYNAME,'Video','Images',imgprefix+'sliderDot_dis.png')) ## LIBRARYNAME
        self.sliderPosition = None
        self.rectHeight = 2
        self.rectBorderColour = wx.LIGHT_GREY
        self.textWidth = 70
        self.margin = 10
        self.doneColor = "#13bd00" # wx.RED 
        self.bufferColor = "#0b7100" # wx.GREEN
        self.sliderWidth = 0
        self.selected = 2
        self.range = (0,1)
        self.dragging = False
        self.allowDragging = False
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)
        self.Bind(wx.EVT_MOUSE_EVENTS, self.OnMouse)
        #self.SetSize((-1,self.bgImage.GetSize()[1]))
        
    def AcceptsFocus(self):
        return False

    def OnEraseBackground(self, event):
        pass # Or None
    
    def OnSize(self, event):
        self.Refresh()
    
    def OnMouse(self, event):
        if not self.allowDragging:
            return
        
        pos = event.GetPosition()
        if event.ButtonDown():
            if self.onSliderButton(pos):
                print >> sys.stderr, 'ProgressSlider: Start drag'
                self.dragging = True
            elif self.onSlider(pos): # click somewhere on the slider
                self.setSliderPosition(pos,True)
        elif event.ButtonUp():
            if self.dragging:
                print >> sys.stderr, 'ProgressSlider: End drag'
                self.setSliderPosition(pos, True)
            self.dragging = False
        elif event.Dragging():
            if self.dragging:
                self.setSliderPosition(pos, False)
        elif event.Leaving():
            if self.dragging:
                self.setSliderPosition(pos,True)
                
    def onSliderButton(self, pos):
        if not self.sliderPosition:
            return False
        x,y = pos
        bx, by = self.sliderPosition
        dotSize = self.dotImage.GetSize()
        return abs(x-bx) < dotSize[0]/2 and abs(y-by)<dotSize[1]/2
        
    def onSlider(self, pos):
        x,y = pos
        width, height = self.GetClientSizeTuple()
        return (x > self.margin and x<= self.margin+self.sliderWidth and \
                abs(y - height/2) < self.rectHeight/2+4)
        
    def setSliderPosition(self, pos, ready):
        x, y = pos
        tmp_progress = (x-self.margin)/float(self.sliderWidth)
        self.progress = min(1.0, max(0.0, tmp_progress))
        self.videoPosition = self
        self.Refresh()
        if ready:
            #theEvent = wx.ScrollEvent(pos=self.progress)
            #self.GetEventHandler().ProcessEvent(theEvent)
            #print >> sys.stderr, 'Posted event'
            #print >> sys.stderr, 'ProgressSlider: Set progress to : %f' % self.progress
            self.sliderChangedAction()
            
    def sliderChangedAction(self):
        self.GetParent().Seek()
            
        
    def setSelected(self, sel):
        self.selected = sel
        self.Refresh()


                
        
    def setBufferFromPieces(self, pieces_complete):
        if not pieces_complete:
            self.videobuffer = 0.0
            return
        last_buffered_piece = 0
        while last_buffered_piece<len(pieces_complete) and pieces_complete[last_buffered_piece]:
            last_buffered_piece+=1
        if last_buffered_piece == len(pieces_complete)-1:
            last_buffered_piece += 1
        
        self.videobuffer = last_buffered_piece/float(len(pieces_complete)) 
        #print >> sys.stderr, 'progress: %d/%d pieces continuous buffer (frac %f)' % \
        #    (last_buffered_piece, len(pieces_complete), self.videobuffer)
        
                    
            
    def SetValue(self, b):
        if self.range[0] == self.range[1]:
            return
        
        if not self.dragging:
            self.progress = max(0.0, min((b - self.range[0]) / float(self.range[1] - self.range[0]), 1.0))
            self.Refresh()
        
    def GetValue(self):
        #print >>sys.stderr, 'ProgressSlider: %f, Range (%f, %f)' % (self.progress, self.range[0], self.range[1])
        return self.progress * (self.range[1] - self.range[0])+ self.range[0]

    def SetRange(self, a,b):
        self.range = (a,b)
    
    def setVideoBuffer(self, buf):
        self.videobuffer = buf
    
    def SetTimePosition(self, timepos, duration):
        self.timeposition = timepos
        self.videoLength = duration

    def ResetTime(self):
        self.videoLength = None
        self.timeposition = None
        self.Refresh()

        
    def formatTime(self, s):
        longformat = time.strftime('%d:%H:%M:%S', time.gmtime(s))
        if longformat.startswith('01:'):
            longformat = longformat[3:]
        while longformat.startswith('00:') and len(longformat) > len('00:00'):
            longformat = longformat[3:]
        return longformat
    
    def OnPaint(self, evt):
        width, height = self.GetClientSizeTuple()
        buffer = wx.EmptyBitmap(width, height)
        #dc = wx.PaintDC(self)
        dc = wx.BufferedPaintDC(self, buffer)
        dc.BeginDrawing()
        dc.Clear()
        
        # Draw background
        bgSize = self.bgImage.GetSize()
        for i in xrange(width/bgSize[0]+1):
            dc.DrawBitmap(self.bgImage, i*bgSize[0],0)
        
        
        # Time strings
        if self.videoLength is not None:
            durationString = self.formatTime(self.videoLength)
        else:
            durationString = '--:--'
        if self.timeposition is not None:
            timePositionString = self.formatTime(self.timeposition)
        else:
            timePositionString = '--:--'
            
        time = '%s / %s' % (timePositionString, durationString)
        
        font = self.GetFont()
        font.SetPointSize(8)
        dc.SetFont(font)
        timeWidth = dc.GetTextExtent(time)[0]
        
        self.sliderWidth = width-(3*self.margin+timeWidth)
        position = self.sliderWidth * self.progress
        self.sliderPosition = position+self.margin, height/2
        self.bufferlength = (self.videobuffer-self.progress) * self.sliderWidth
        self.bufferlength = min(self.bufferlength, self.sliderWidth-position)
        
        if width > 3*self.margin+timeWidth:
            # Draw slider rect
            dc.SetPen(wx.Pen(self.rectBorderColour, 2))
            dc.DrawRectangle(self.margin,height/2-self.rectHeight/2, self.sliderWidth, self.rectHeight)
            # Draw slider rect inside
            dc.SetPen(wx.Pen(self.doneColor, 0))
            dc.SetBrush(wx.Brush(self.doneColor))
            smallRectHeight = self.rectHeight - 2
            dc.DrawRectangle(self.margin,height/2-smallRectHeight/2, position, smallRectHeight)
            dc.SetBrush(wx.Brush(self.bufferColor))
            dc.SetPen(wx.Pen(self.bufferColor, 0))
            dc.DrawRectangle(position+self.margin,height/2-smallRectHeight/2, self.bufferlength, smallRectHeight)
            # draw circle
            dotSize = self.dotImage.GetSize()
            if self.selected == 2:
                dc.DrawBitmap(self.dotImage_dis, position+self.margin-dotSize[0]/2, height/2-dotSize[1]/2, True)
            else:
                dc.DrawBitmap(self.dotImage, position+self.margin-dotSize[0]/2, height/2-dotSize[1]/2, True)
        if width > 2*self.margin+timeWidth:
            # Draw times
            dc.DrawText(time, width-self.margin-timeWidth, height/2-dc.GetCharHeight()/2)

        dc.EndDrawing()

    def EnableDragging(self):
        self.allowDragging = True
        self.setSelected(1)
        
    def DisableDragging(self):
        self.allowDragging = False
        self.setSelected(2)

 
class VolumeSlider(wx.Panel):
    
    def __init__(self, parent, utility, imgprefix=''):
        self.progress      = 0.0
        self.position = 0
        
        #wx.Control.__init__(self, parent, -1)
        wx.Panel.__init__(self, parent, -1)
        self.SetMaxSize((150,25))
        self.SetMinSize((150,25))
        self.SetBackgroundColour(wx.WHITE)
        self.utility = utility
        self.bgImage = wx.Bitmap(os.path.join(self.utility.getPath(), LIBRARYNAME,'Video','Images',imgprefix+'background.png')) ## LIBRARYNAME
        self.dotImage = wx.Bitmap(os.path.join(self.utility.getPath(), LIBRARYNAME,'Video','Images',imgprefix+'sliderVolume.png')) ## LIBRARYNAME
        self.sliderPosition = None
        self.rectHeight = 2
        self.rectBorderColour = wx.LIGHT_GREY
        self.margin = 10
        self.cursorsize = [4,19]
        self.doneColor = wx.BLACK #wx.RED
        self.sliderWidth = 0
        self.range = (0,1)
        self.dragging = False
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)
        self.Bind(wx.EVT_MOUSE_EVENTS, self.OnMouse)
        #self.SetSize((-1,self.bgImage.GetSize()[1]))
        
    def AcceptsFocus(self):
        return False

    def OnEraseBackground(self, event):
        pass # Or None
    
    def OnSize(self, event):
        self.Refresh()
    
    def OnMouse(self, event):
        pos = event.GetPosition()
        if event.ButtonDown():
            if self.onSliderButton(pos):
                print >> sys.stderr, 'VolumeSlider: Start drag'
                self.dragging = True
            elif self.onSlider(pos): # click somewhere on the slider
                self.setSliderPosition(pos,True)
        elif event.ButtonUp():
            if self.dragging:
                print >> sys.stderr, 'VolumeSlider: End drag'
                self.setSliderPosition(pos, True)
            self.dragging = False
        elif event.Dragging():
            if self.dragging:
                self.setSliderPosition(pos, False)
        elif event.Leaving():
            if self.dragging:
                self.setSliderPosition(pos,True)
                
    def onSliderButton(self, pos):
        if not self.sliderPosition:
            return False
        x,y = pos
        bx, by = self.sliderPosition
        extraGrip = 3 # 3px extra grip on sliderButton
        return abs(x-bx) < self.cursorsize[0]/2+extraGrip and abs(y-by)<self.cursorsize[1]/2
        
    def onSlider(self, pos):
        x,y = pos
        width, height = self.GetClientSizeTuple()
        return (x > self.margin and x<= self.margin+self.sliderWidth and \
                abs(y - height/2) < self.rectHeight/2+4)
        
    def setSliderPosition(self, pos, ready):
        x, y = pos
        tmp_progress = (x-self.margin)/float(self.sliderWidth)
        self.progress = min(1.0, max(0.0, tmp_progress))
        self.videoPosition = self
        self.Refresh()
        if ready:
            #theEvent = wx.ScrollEvent(pos=self.progress)
            #self.GetEventHandler().ProcessEvent(theEvent)
            #print >> sys.stderr, 'Posted event'
            print >> sys.stderr, 'VolumeSlider: Set progress to : %f' % self.progress
            self.sliderChangedAction()
            
    def sliderChangedAction(self):
        self.GetParent().SetVolume()
            
            
    def SetValue(self, b):
        if not self.dragging:
            self.progress = min((b - self.range[0]) / float(self.range[1] - self.range[0]), 1.0)
            self.Refresh()
        
    def GetValue(self):
        print >>sys.stderr, 'VolumeSlider: %f, Range (%f, %f)' % (self.progress, self.range[0], self.range[1])
        return self.progress * (self.range[1] - self.range[0])+ self.range[0]

    def SetRange(self, a,b):
        self.range = (a,b)
    
    def OnPaint(self, evt):
        width, height = self.GetClientSizeTuple()
        buffer = wx.EmptyBitmap(width, height)
        #dc = wx.PaintDC(self)
        dc = wx.BufferedPaintDC(self, buffer)
        dc.BeginDrawing()
        dc.Clear()
        
        # Draw background
        bgSize = self.bgImage.GetSize()
        for i in xrange(width/bgSize[0]+1):
            dc.DrawBitmap(self.bgImage, i*bgSize[0],0)
        
        
        self.sliderWidth = width-(2*self.margin)
        position = self.sliderWidth * self.progress
        self.sliderPosition = position+self.margin, height/2
        
        
        if width > 2*self.margin:
            # Draw slider rect
            dc.SetPen(wx.Pen(self.rectBorderColour, 2))
            dc.DrawRectangle(self.margin,height/2-self.rectHeight/2, self.sliderWidth, self.rectHeight)
            # Draw slider rect inside
            dc.SetPen(wx.Pen(self.doneColor, 0))
            dc.SetBrush(wx.Brush(self.doneColor))
            smallRectHeight = self.rectHeight - 2
            dc.DrawRectangle(self.margin,height/2-smallRectHeight/2, position, smallRectHeight)
            # draw slider button
            dotSize = self.dotImage.GetSize()
            dc.DrawBitmap(self.dotImage, position+self.margin-dotSize[0]/2, height/2-dotSize[1]/2, True)
        dc.EndDrawing()

        
