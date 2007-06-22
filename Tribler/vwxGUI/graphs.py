from Tribler.vwxGUI.GuiUtility import GUIUtility
from ABC.Torrent.abctorrent import ABCTorrent
from Utility.constants import * #IGNORE:W0611
import threading
# Needs Numeric or numarray or NumPy
try:
    import numpy as _Numeric
except:
    try:
        import numarray as _Numeric  #if numarray is used it is renamed Numeric
    except:
        try:
            import Numeric as _Numeric
        except:
            msg = "This module requires the Numeric/numarray or NumPy module,"
            msg += "which could not be imported.  It probably is not installed"
            msg += "(it's not part of the standard Python distribution). See the"
            msg += "Numeric Python site (http://numpy.scipy.org) for information on"
            msg += "downloading source or binaries."
            raise ImportError, "Numeric,numarray or NumPy not found. \n\n" + msg
from wx.lib.plot import *
 
    
class MyTimer(threading.Thread):
    def __init__(self, callback):
        threading.Thread.__init__(self)
        self.status = 0 #0=initialized, 1=started, 2=running, 3=should stop, 4=stopped
        self.delay = 0
        self.period = -1
        self.callback = callback
        self.pause_ev = threading.Event() #should pause?
        self.pause_ev.set()
        self.notify = threading.Event()
        
    def start(self, period, delay=0, paused=True):
        self.status = 1
        self.delay = delay
        self.period = period
        if paused:
            self.pause() #start it paused, call resume to really start it
        threading.Thread.start(self)
    
        
    def pause(self):
        #check first if it's started
        if self.status < 1:
            self.start()
        self.pause_ev.clear()
        
    def resume(self):
        #check first if it's started
        if self.status < 1:
            self.start()
        self.pause_ev.set()
    
    def stop(self):
        self.status = 3
        self.notify.set()
        
    def wait(self, period):
        if self.status >= 3 or period < 0 or self.notify.isSet():
            return 1 #means it is stopped
        if period == 0:
            return 0 #don't wait...
        self.pause_ev.wait()
        self.notify.wait(period) #during waiting, an event.set might have been called
        if self.notify.isSet():
            return 1
        return 0 #means that wait went fine
        
    def run(self):
        self.status=2
        if self.wait(self.delay):
            self.status=4
            return #wait decided that timer is stopped
        if self.callback is None:
            self.status=4
            return
        wx.CallAfter(self.callback)
        while self.wait(self.period) == 0:
            if self.callback is None:
                self.status=4
                return
            wx.CallAfter(self.callback)
        self.status = 4


class StatsPanel(PlotCanvas):
    """ draws a plot of download rate of each torrent and the total one.
        the same for upload.
        on tooltip it shows informations about the torrent
        """
 
    def __init__(self, parent):
        PlotCanvas.__init__(self, parent)

        self.guiUtility = GUIUtility.getInstance()
        self.utility = self.guiUtility.utility
        
        self.plot_graphics = None
        self.visible = False #visibility flag set manually
        self.uploadIsNegative = False #flag to set upload view as negative
        self.showTotal = True
        self.showTotal2 = False
        self.showAll = False #unused yet
        self.currentItem = None #unused yet
#        self.utility = frame.utility # get the utility object of parent frame, should be there!
        
        # Create mouse event for showing cursor coords in status bar
        #self.Bind(wx.EVT_LEFT_DOWN, self.OnMouseLeftDown, None, wx.NewId())
        #self.mouseLeftDownText = None
        #self.mouseX, self.mouseY = 0,0
        # Show closest point when enabled
        #self.Bind(wx.EVT_MOTION, self.OnMotion, None, wx.NewId())
        # Save file key action
        #self.Bind(wx.EVT_CHAR, self.OnChar, self, wx.NewId())
        # self.Bind(wx.EVT_KEY_DOWN, self.OnChar, self, wx.NewId())
        # Paint event
        wx.EVT_PAINT( self, self.OnPaint)
        #Bar Graph Example
        """Just to reset the fonts back to the PlotCanvas defaults"""
        self.SetFont(wx.Font(10,wx.SWISS,wx.NORMAL,wx.NORMAL))
        self.SetFontSizeAxis(10)
        self.SetFontSizeLegend(7)
        #self.SetEnablePointLabel(True)
        #self.SetEnableZoom(False)
        self.SetGridColour('gray')
        self.SetShowScrollbars(False)
        self.SetEnableLegend(True)   #turn on Legend
        self.SetEnableGrid(True)     #turn on Grid
        self.SetXSpec('none')        #turns off x-axis scale
        self.SetYSpec('auto')
        self.my_DataDict = None
        # history of downloading and uploading rates
        # as dictionary: 'total down/up':array, torrent1: array, torrent2: array, and so on
        self.down_data = {}
        self.up_data = {}
        # first call to create the plot
        #self.updateData()
        # register the timer to periodically call updateData
        #ID_Timer = wx.NewId()
        #self.timer = wx.Timer(self, ID_Timer)
        #self.Bind( wx.EVT_TIMER, self.OnMyTimer, self.timer)     
        #self.timer.Start(5000)
        self.timer = MyTimer(self.OnMyTimer)
        self.timer.start(0.5)
                
            
        
    def setVisible(self, isVisible):
        """set the visibility flag and also clears the graph history"""
        #print "set visible: ", isVisible
        if self.visible == isVisible:
            return
        self.visible = isVisible
        if not self.visible:
            self.timer.pause()
            self.plot_graphics=None
            self.down_data = {}
            self.up_data = {}
        else:
            # first call to create the plot
            self.updateData()
            self.timer.resume()
            #self.Refresh()
    
    def setNegativeUpload(self, isUploadNegative):
        if self.uploadIsNegative == isUploadNegative:
            return
        self.uploadIsNegative = isUploadNegative
        self.plot_graphics=None
        self.down_data = {}
        self.up_data = {}
        self.Refresh()
        
    def Draw(self, graphics, xAxis = None, yAxis = None, dc = None):
        """
        ##########################
        Rewrite of Draw function in plot package to have only positive values on y axis below and above 0
        ##########################
        Draw objects in graphics with specified x and y axis.
        graphics- instance of PlotGraphics with list of PolyXXX objects
        xAxis - tuple with (min, max) axis range to view
        yAxis - same as xAxis
        dc - drawing context - doesn't have to be specified.    
        If it's not, the offscreen buffer is used
        """
        # check Axis is either tuple or none
        if type(xAxis) not in [type(None),tuple]:
            raise TypeError, "xAxis should be None or (minX,maxX)"
        if type(yAxis) not in [type(None),tuple]:
            raise TypeError, "yAxis should be None or (minY,maxY)"
             
        # check case for axis = (a,b) where a==b caused by improper zooms
        if xAxis != None:
            if xAxis[0] == xAxis[1]:
                return
        if yAxis != None:
            if yAxis[0] == yAxis[1]:
                return
            
        if dc == None:
            # sets new dc and clears it 
            dc = wx.BufferedDC(wx.ClientDC(self.canvas), self._Buffer)
            dc.Clear()
            
        dc.BeginDrawing()
        # dc.Clear()
        
        # set font size for every thing but title and legend
        dc.SetFont(self._getFont(self._fontSizeAxis))

        # sizes axis to axis type, create lower left and upper right corners of plot
        if xAxis == None or yAxis == None:
            # One or both axis not specified in Draw
            p1, p2 = graphics.boundingBox()     # min, max points of graphics
            if xAxis == None:
                xAxis = self._axisInterval(self._xSpec, p1[0], p2[0]) # in user units
            if yAxis == None:
                yAxis = self._axisInterval(self._ySpec, p1[1], p2[1])
            # Adjust bounding box for axis spec
            p1[0],p1[1] = xAxis[0], yAxis[0]     # lower left corner user scale (xmin,ymin)
            p2[0],p2[1] = xAxis[1], yAxis[1]     # upper right corner user scale (xmax,ymax)
        else:
            # Both axis specified in Draw
            p1= _Numeric.array([xAxis[0], yAxis[0]])    # lower left corner user scale (xmin,ymin)
            p2= _Numeric.array([xAxis[1], yAxis[1]])     # upper right corner user scale (xmax,ymax)

        self.last_draw = (graphics, xAxis, yAxis)       # saves most recient values

        # Get ticks and textExtents for axis if required
        if self._xSpec is not 'none':        
            xticks = self._ticks(xAxis[0], xAxis[1])
            xTextExtent = dc.GetTextExtent(xticks[-1][1])# w h of x axis text last number on axis
        else:
            xticks = None
            xTextExtent= (0,0) # No text for ticks
        if self._ySpec is not 'none':
            yticks = self._ticks(yAxis[0], yAxis[1])
            #print "yticks: ",yticks
            # remove the minus from the y ticks
            # for that, build another yticks
            yticks_poz = []
            for pair in yticks:
                if pair[1][0] == '-':
                    yticks_poz.append((pair[0],pair[1][1:]))
                else:
                    yticks_poz.append(pair)
            yticks = yticks_poz
            yTextExtentBottom= dc.GetTextExtent(yticks[0][1])
            yTextExtentTop   = dc.GetTextExtent(yticks[-1][1])
            yTextExtent= (max(yTextExtentBottom[0],yTextExtentTop[0]),
                        max(yTextExtentBottom[1],yTextExtentTop[1]))
        else:
            yticks = None
            yTextExtent= (0,0) # No text for ticks

        # TextExtents for Title and Axis Labels
        titleWH, xLabelWH, yLabelWH= self._titleLablesWH(dc, graphics)

        # TextExtents for Legend
        legendBoxWH, legendSymExt, legendTextExt = self._legendWH(dc, graphics)

        # room around graph area
        rhsW= max(xTextExtent[0], legendBoxWH[0]) # use larger of number width or legend width
        lhsW= yTextExtent[0]+ yLabelWH[1]
        bottomH= max(xTextExtent[1], yTextExtent[1]/2.)+ xLabelWH[1]
        topH= yTextExtent[1]/2. + titleWH[1]
        textSize_scale= _Numeric.array([rhsW+lhsW,bottomH+topH]) # make plot area smaller by text size
        textSize_shift= _Numeric.array([lhsW, bottomH])          # shift plot area by this amount

        # drawing title and labels text
        dc.SetFont(self._getFont(self._fontSizeTitle))
        titlePos= (self.plotbox_origin[0]+ lhsW + (self.plotbox_size[0]-lhsW-rhsW)/2.- titleWH[0]/2.,
                 self.plotbox_origin[1]- self.plotbox_size[1])
        dc.DrawText(graphics.getTitle(),titlePos[0],titlePos[1])
        dc.SetFont(self._getFont(self._fontSizeAxis))
        xLabelPos= (self.plotbox_origin[0]+ lhsW + (self.plotbox_size[0]-lhsW-rhsW)/2.- xLabelWH[0]/2.,
                 self.plotbox_origin[1]- xLabelWH[1])
        dc.DrawText(graphics.getXLabel(),xLabelPos[0],xLabelPos[1])
        yLabelPos= (self.plotbox_origin[0],
                 self.plotbox_origin[1]- bottomH- (self.plotbox_size[1]-bottomH-topH)/2.+ yLabelWH[0]/2.)
        if graphics.getYLabel():  # bug fix for Linux
            dc.DrawRotatedText(graphics.getYLabel(),yLabelPos[0],yLabelPos[1],90)

        # drawing legend makers and text
        if self._legendEnabled:
            self._drawLegend(dc,graphics,rhsW,topH,legendBoxWH, legendSymExt, legendTextExt)

        # allow for scaling and shifting plotted points
        scale = (self.plotbox_size-textSize_scale) / (p2-p1)* _Numeric.array((1,-1))
        shift = -p1*scale + self.plotbox_origin + textSize_shift * _Numeric.array((1,-1))
        self._pointScale= scale  # make available for mouse events
        self._pointShift= shift        
        self._drawAxes(dc, p1, p2, scale, shift, xticks, yticks)
        
        graphics.scaleAndShift(scale, shift)
        graphics.setPrinterScale(self.printerScale)  # thicken up lines and markers if printing
        
        # set clipping area so drawing does not occur outside axis box
        ptx,pty,rectWidth,rectHeight= self._point2ClientCoord(p1, p2)
        dc.SetClippingRegion(ptx,pty,rectWidth,rectHeight)
        # Draw the lines and markers
        #start = _time.clock()
        graphics.draw(dc)
        # print "entire graphics drawing took: %f second"%(_time.clock() - start)
        # remove the clipping region
        dc.DestroyClippingRegion()
        dc.EndDrawing()
        #self._adjustScrollbars()

    def _drawLegend(self,dc,graphics,rhsW,topH,legendBoxWH, legendSymExt, legendTextExt):
        """
        #####################################################################
        rewrite of function in plot to show a box instead of a line in legend
        #####################################################################
        Draws legend symbols and text"""
        # top right hand corner of graph box is ref corner
        trhc= self.plotbox_origin+ (self.plotbox_size-[rhsW,topH])*[1,-1]
        legendLHS= .091* legendBoxWH[0]  # border space between legend sym and graph box
        lineHeight= max(legendSymExt[1], legendTextExt[1]) * 1.1 #1.1 used as space between lines
        dc.SetFont(self._getFont(self._fontSizeLegend))
        for i in range(len(graphics)):
            o = graphics[i]
            s= i*lineHeight
            if isinstance(o,PolyMarker):
                # draw marker with legend
                pnt= (trhc[0]+legendLHS+legendSymExt[0]/2., trhc[1]+s+lineHeight/2.)
                o.draw(dc, self.printerScale, coord= _Numeric.array([pnt]))
            elif isinstance(o,PolyLine):
                # draw line with legend
                pnt1= (trhc[0]+legendLHS, trhc[1]+s) #+lineHeight/2.)
                pnt2= (trhc[0]+legendLHS+legendSymExt[0], trhc[1]+s+lineHeight) #/2.)
                #o.draw(dc, self.printerScale, coord= _Numeric.array([pnt1,pnt2]))
                # draw a box instead of a line using the line's properties
                colour = o.attributes['colour']
                width = o.attributes['width'] * self.printerScale
                style= o.attributes['style']
                if not isinstance(colour, wx.Colour):
                    colour = wx.NamedColour(colour)
                pen = wx.Pen('black')#, width, style)
                #pen.SetCap(wx.CAP_BUTT)
                dc.SetPen(pen)     
                dc.SetBrush(wx.Brush(colour))
                dc.DrawRectangle( pnt1[0], pnt1[1]+1, pnt2[0]-pnt1[0], pnt2[1]-pnt1[1]-2)
            else:
                raise TypeError, "object is neither PolyMarker or PolyLine instance"
            # draw legend txt
            pnt= (trhc[0]+legendLHS+legendSymExt[0], trhc[1]+s+lineHeight/2.-legendTextExt[1]/2)
            dc.DrawText(o.getLegend(),pnt[0],pnt[1])
        dc.SetFont(self._getFont(self._fontSizeAxis)) # reset
        
        
    def OnMyTimer(self, event=None):
        #print event
        print "OnMyTimer [StatsPanel]"
        self.updateData()
        
    def updateData(self):
        if not self.visible:
            return #don't compute new things if it is not visible
#        if self.IsShown():
#            print "panel is visible"
#        else:
#            print "graph stats is not visible"
        print "UpldatingData [StatsPanel]"
        MAX_POINTS = 61
        lines = []
        upload_sign = 1
        if self.uploadIsNegative:
            upload_sign = -1
        # init first and last id
        first_id = 0
        last_id = MAX_POINTS-1
        if len(self.down_data.keys()) > 0:
            graph_item_name = self.down_data.keys()[0]
            first_id = self.down_data[graph_item_name][0][0]
            ddlen = len(self.down_data[graph_item_name])
            last_id = self.down_data[graph_item_name][ddlen-1][0]+1
        if self.showTotal:
            if 'total' in self.down_data:
                ddlen = len(self.down_data['total'])
                # compute the last id
                last_id = self.down_data['total'][ddlen-1][0]+1
                self.down_data['total'].pop(0)
                self.down_data['total'].append((last_id, self.utility.queue.totals_kb['down']))
                self.up_data['total'].pop(0)
                self.up_data['total'].append((last_id, upload_sign*self.utility.queue.totals_kb['up']))
    #            self.up_data['total'].append((last_id, -self.utility.queue.totals_kb['up']))
                # compute first id after the removal
                first_id = self.down_data['total'][0][0]
            else:
                self.down_data['total'] = []
                self.up_data['total'] = []
                first_id = 0
                last_id = MAX_POINTS-1
                for i in range(0,MAX_POINTS-1): 
                    self.down_data['total'].append((i,0))
                    self.up_data['total'].append((i,0))
                self.down_data['total'].append((last_id, self.utility.queue.totals_kb['down']))
                self.up_data['total'].append((last_id, upload_sign*self.utility.queue.totals_kb['up']))
            lines.append(PolyLine(self.down_data['total'], legend= 'Total Download', colour='green', width=2))
            lines.append(PolyLine(self.up_data['total'], legend= 'Total Upload', colour='red', width=2))

        total_down = total_up = 0.0
        ALMOST_ZERO =  0.0001
        # get each torrent that's downloading/uploading and put it in plot
        for ABCTorrentTemp in self.utility.torrents["active"].keys():
            if ABCTorrentTemp.status.value != STATUS_PAUSE:
                downrate = ABCTorrentTemp.getColumnValue(COL_DLSPEED)
                uprate = ABCTorrentTemp.getColumnValue(COL_ULSPEED)
                
                up_kb = (uprate / 1024.0)
                down_kb = (downrate / 1024.0)
                if self.showTotal2:
                    if down_kb > ALMOST_ZERO:
                        total_down = total_down + down_kb
                    if up_kb > ALMOST_ZERO:
                        total_up = total_up + up_kb
                
                #print repr(ABCTorrentTemp)
                # check if this torrent has an active history or if the current rate up/down is relevant
                # greater than 0
                if ABCTorrentTemp in self.down_data:
                    down_data = self.down_data[ABCTorrentTemp]
                    down_data.pop(0)
                    if down_kb > ALMOST_ZERO:
                        down_data.append((last_id, down_kb))
                    else:
                        #check to see if the rest of the points are 0, and if so, delete the information
                        bAllZero = True
                        for i in range(len(down_data)):
                            if down_data[i][1] > ALMOST_ZERO:
                                bAllZero = False
                                break
                        if bAllZero:
                            #delete the key ABCTorrentTemp
                            del self.down_data[ABCTorrentTemp]
                else:
                    #adds a torrent that is active but not plotted
                    #should check if the case to create a history (value <> 0)
                    if down_kb > ALMOST_ZERO:
                        down_data = []
                        for i in range(first_id,last_id): 
                            down_data.append((i,0))
                        down_data.append((last_id,down_kb))
                        self.down_data[ABCTorrentTemp] = down_data
                if ABCTorrentTemp in self.down_data:
                    # to generate color for torrent, get the first 6 characters from infohash and combine them
                    # with green for download and red for upload
                    title = 'DL %s' % ABCTorrentTemp.getColumnValue(COL_TITLE)
                    if len(title) > 15:
                        title = title[:15]
                    lines.append(PolyLine(self.down_data[ABCTorrentTemp], legend= title, colour=self.getColor( ABCTorrentTemp.infohash, 'DL')))
                #upload
                if ABCTorrentTemp in self.up_data:
                    up_data = self.up_data[ABCTorrentTemp]
                    up_data.pop(0)
                    if up_kb > ALMOST_ZERO:
                        up_data.append((last_id, upload_sign*up_kb))
#                        up_data.append((last_id, -up_kb))
                    else:
                        #check to see if the rest of the points are 0, and if so, delete the information
                        bAllZero = True
                        for i in range(len(up_data)):
                            if up_data[i][1] > ALMOST_ZERO:
                                bAllZero = False
                                break
                        if bAllZero:
                            #delete the key ABCTorrentTemp
                            del self.up_data[ABCTorrentTemp]
                else:
                    #adds a torrent that is active but not plotted
                    #should check if the case to create a history (value <> 0)
                    if up_kb > ALMOST_ZERO:
                        up_data = []
                        for i in range(first_id,last_id): 
                            up_data.append((i,0))
                        up_data.append((last_id,upload_sign*up_kb))
                        self.up_data[ABCTorrentTemp] = up_data
                if ABCTorrentTemp in self.up_data:
                    # to generate color for torrent, get the first 6 characters from infohash and combine them
                    # with green for download and red for up
                    title = 'UP %s' % ABCTorrentTemp.getColumnValue(COL_TITLE)
                    if len(title) > 15:
                        title = title[:15]
                    lines.append(PolyLine(self.up_data[ABCTorrentTemp], legend= title, colour=self.getColor( ABCTorrentTemp.infohash, 'UP')))
        #remove all torrents that are no more active
        for PlotTorrent in self.down_data.keys():
            if isinstance(PlotTorrent,ABCTorrent):
                if not PlotTorrent in self.utility.torrents["active"]:
                    #print "deleting dw torrent ",PlotTorrent.getColumnValue(COL_TITLE)
                    del self.down_data[PlotTorrent]
        for PlotTorrent in self.up_data.keys():
            if isinstance(PlotTorrent,ABCTorrent):
                if not PlotTorrent in self.utility.torrents["active"]:
                    #print "deleting up torrent ",PlotTorrent.getColumnValue(COL_TITLE)
                    del self.up_data[PlotTorrent]
        #compute a second totals
        if self.showTotal2:
            if 'total_bis' in self.down_data:
                ddlen = len(self.down_data['total_bis'])
                # compute the last id
                last_id = self.down_data['total_bis'][ddlen-1][0]+1
                self.down_data['total_bis'].pop(0)
                self.down_data['total_bis'].append((last_id, total_down))
                self.up_data['total_bis'].pop(0)
                self.up_data['total_bis'].append((last_id, upload_sign*total_up))
                # compute first id after the removal
                first_id = self.down_data['total_bis'][0][0]
            else:
                self.down_data['total_bis'] = []
                self.up_data['total_bis'] = []
                first_id = 0
                last_id = MAX_POINTS-1
                for i in range(0,MAX_POINTS-1): 
                    self.down_data['total_bis'].append((i,0))
                    self.up_data['total_bis'].append((i,0))
                self.down_data['total_bis'].append((last_id, total_down))
                self.up_data['total_bis'].append((last_id, upload_sign*total_up))
            lines.append(PolyLine(self.down_data['total_bis'], legend= 'Total Download II', colour='blue', width=2))
            lines.append(PolyLine(self.up_data['total_bis'], legend= 'Total Upload II', colour='brown', width=2))


        self.first_id=first_id
        self.last_id=last_id
        if len(lines) > 0:
            self.plot_graphics = PlotGraphics( lines,"up/down rates", "Time", "Rate [kb/s]")
        else:
            self.plot_graphics = None
        self.Refresh()
#        self.timer.Start(5000)
##        ## draw
##        # Bar graph
##        self.lines = []
##        color_increment=125
##        if len(self.data)>0:
##            color_increment = 255/len(self.data)
##        color = 0
##        max_color = 200
##        for i in xrange(len(self.data)):
##            # print "similarity with ",self.data[i]['ip']," is ",self.data[i]['similarity']
##            if color>max_color: color=max_color
##            points=[(i+1,0), (i+1,self.data[i]['similarity'])] # self.data[i]['similarity']
##            line = PolyLine(points, colour=wx.Colour(color,color,color), legend=self.data[i]['ip'], width=10)
##            self.lines.append(line)
##            color += color_increment
##        if len(self.lines)==0:
##            return None
##        return PlotGraphics( self.lines, "Similarity between me and other peers descending", "Peers", "Similarity (%)")
        
    def getColor( self, infohash, type='DL'):
        sred = infohash[0:2]
        sgreen = infohash[2:4]
        sblue = infohash[4:6]
        if type == 'DL':
            return '#%s%s%s' % (sred,'FF',sblue)
        elif type == 'UP':
            return '#%s%s%s' % ('FF',sgreen,sblue)
        else:
            return '#%s%s%s' % (sred,sgreen,sblue)
        
    def OnPaint(self, event):
        print "OnPaint [StatsPanel]"

        PlotCanvas.OnPaint(self, event)
        dc = wx.PaintDC(self.canvas)

        if self.plot_graphics != None:
            self.Draw(self.plot_graphics, xAxis= (self.first_id, self.last_id), dc=dc)
            
        # draw the tooltip self.my_DataDict
        if self.my_DataDict:
            #print self.my_DataDict
            mDataDict = self.my_DataDict
            dc.SetPen(wx.BLACK_PEN)
            dc.SetBrush(wx.WHITE_BRUSH)
            dc.SetFont(wx.Font(8, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
            
            sx, sy = mDataDict["scaledXY"] #scaled x,y of lowest point on the polyline
            cNum = mDataDict["curveNum"]
            #make a string to display
            s = ''
            bFirst = True
            for torrent_info in self.data[cNum-1]['torrents_list']:
                if bFirst:
                    bFirst = False
                else:
                    s+= '\n'
                s += torrent_info['info']['name']
            width, height, line_height = dc.GetMultiLineTextExtent(s)
            if width > 350:
                width = 350
            count = 0
            if height > 200:
                count = int(200/line_height)
                height = count*line_height
                #print "count limited: 400/%d=%d" % (line_height,count)
            else:
                count = len(self.data[cNum-1]['torrents_list'])
            #print "count=",count
            dc.DrawRectangle( sx, sy, width+6, -height-6)
            text_start_height = sy-3-height
            index = 0
            for torrent_info in self.data[cNum-1]['torrents_list']:
                if index >= count:
                    break
                index += 1
                #color torrents based on status: { downloading (green), seeding (yellow),} good (blue), unknown(black), dead (red); 
                if torrent_info['status'] == 'good':
                    dc.SetTextForeground("blue")
                elif torrent_info['status'] == 'unknown':
                    dc.SetTextForeground("black")
                elif torrent_info['status'] == 'dead':
                    dc.SetTextForeground("red")
                #dc.DrawText( torrent_info['info']['name'], sx+3, text_start_height)
                text = torrent_info['info']['name']
                lw, lh = dc.GetTextExtent( text)
                if lw > width:
                    #print "processing ",text
                    #find the extension and last 2-3 letters before it and then insert "..."
                    end_text = ""
                    pos = len(text)-1
                    while pos>=0:
                        if text[pos] == ".":
                            break
                        pos -= 1
                    if pos>=0:
                        end_text = text[pos:]
                        text = text[:pos]
                        #print "extension is",end_text,"remaining text is",text
                    
                    end_text = text[len(text)-3:] + end_text
                    text = text[:len(text)-3]
                    end_text = "..." + end_text
                    #print "end text is",end_text
                    while lw > width and len(text)>0:
                        text = text[:len(text)-1]
                        lw, lh = dc.GetTextExtent(text+end_text)
                    #print "remaining text is",text
                    text += end_text
                dc.DrawLabel( text, wx.Rect( sx+3, text_start_height, width, line_height))
                text_start_height += line_height
        
        event.Skip(False)

    def OnMouseLeftDownA(self,event):
        self.mouseLeftDownText= "Left Mouse Down at Point: (%.4f, %.4f)" % self.GetXY(event)
        self.mouseX, self.mouseY = event.GetX(), event.GetY()
        print "mouse left down"
        self.Refresh()
        # self.SetStatusText(s)
        event.Skip()            #allows plotCanvas OnMouseLeftDown to be called
        
    def OnMotionA(self, event):
        # show tooltip
        pointScaled= True
        pntXY = self.GetXY(event)
        # for that, first search for the polyline that contains the mouse cursor
        for index in range(len(self.lines)):
            line = self.lines[index]
            width = line.attributes['width'] * self.printerScale
            width = width/2
            # take each pair of two points and check if mouse inside it
            if pointScaled == True:
                #Using screen coords
                p = line.scaled
                pxy = line.currentScale * _Numeric.array(pntXY)+ line.currentShift
                # compute list of distances between points
            else:
                #Using user coords
                p = line.points
                pxy = _Numeric.array(pntXY)
            my_last = len(p)-1
            my_first = 0
            my_point = p[my_last]
            # check x axis
            if my_point[0] + width > pxy[0] and my_point[0] - width < pxy[0]:
                # check y axis
                if my_point[1] < pxy[1]:
                    # found the line, so break
                    # print "found line ",index," with point:",my_point
                    #self.my_DataDict= {"curveNum":index, "legend":'', "pIndex":'',\
                     #       "pointXY":line.points[my_last], "scaledXY":line.scaled[my_last]}
                    self.my_DataDict = {"curveNum":index, "scaledXY":line.scaled[my_first] }
                    # self.UpdatePointLabel(mDataDict)
                    self.Refresh()
                    break
        else:
            if self.my_DataDict != None:
                #print "hovering over nothing"
                self.my_DataDict = None
                self.Refresh()
        event.Skip()           #go to next handler
        
    def OnCharA(self, event):
        print "on char:",event.GetKeyCode()
        if ( event.GetKeyCode() == 's' or event.GetKeyCode() == 'S' or event.GetKeyCode()==19 ):
            self.SaveFile()
        event.Skip()
