"""" replaces CanvasItem objects from Tk:
Oval, Text and Line
"""

import wx
import host
# from host import cx, cy

class CanvasObjects:
    def __init__ (self, canvas):
        self.canvas = canvas
        self.objects = []
        self.dcx, self.dcy = 0, 0 # actual distance from the real center of the window to the cx,cy from host
        self.width, self.height = 0, 0 #actual size of the drawing area, usefull for items not stuck to the center
        
    def lower(self, item):
        # the item should be drawn on the background, with all others above him
        # for that, get it and put it in front of the list, so that it is drawn first and then all other
        try:
            self.objects.remove(item)
            self.objects.insert(0, item)
        except ValueError:
            pass
        
    def lift(self, item):
        # the item should be drawn on the foreground, with all others below it
        # for that, get it and put it at the end of the list, so that it is drawn last
        try:
            self.objects.remove(item)
            self.objects.append( item)
        except ValueError:
            pass
        
    def remove(self, item):
        try:
            self.objects.remove(item)
        except ValueError:
            pass

    def CanvasItem(self, type, opts):
        item = MyCanvasObject(self, type, opts)
        self.objects.append(item)
        return item
        
    def Line(self, opts=None):
        return self.CanvasItem("line", opts)
    
    @staticmethod
    def createLine(canvas, opts):
        return canvas.dc_objects.Line(opts)
    
    def Oval(self, opts=None):
        return self.CanvasItem("oval", opts)
    
    @staticmethod
    def createOval(canvas, x1, y1, x2, y2):
        # print canvas.dc_objects.__name__
        return canvas.dc_objects.Oval({'x1':x1, 'y1':y1, 'x2':x2, 'y2':y2})
        
    def Text(self, opts=None):
        return self.CanvasItem("text", opts)
    
    @staticmethod
    def createText(canvas, x, y, font=None, justify=None, anchor=None, text=None):
        return canvas.dc_objects.Text({'x1':x, 'y1':y, 'font':font, 'justify':justify, 'anchor':anchor, 'text':text})
        
    def OnPaint(self, dc):
        # print "now should draw something..."
##        try:
##            dc = wx.BufferedDC(self.canvas)
##        except:
##            dc = wx.ClientDC(self.canvas)
##        dc.Clear()
        for object in self.objects:
            # check first to see if there is something to draw
            if object.type == 'text' and object.options['text']=='':
                continue
            x1 = 'x1' in object.options and object.options['x1'] or 0
            y1 = 'y1' in object.options and object.options['y1'] or 0
            x2 = 'x2' in object.options and object.options['x2'] or 0
            y2 = 'y2' in object.options and object.options['y2'] or 0
            w = x2 - x1
            h = y2 - y1
            if object.isRelativePosX:
                x1 += self.dcx
                x2 += self.dcx
            else:
                if x1<0: x1 = self.width + x1
                if x2<0: x2 = self.width + x2
            if object.isRelativePosY:
                y1 += self.dcy
                y2 += self.dcy
            else:
                if y1<0: y1 = self.height + y1
                if y2<0: y2 = self.height + y2
            # oldPen = None
            # oldBrush = None
            oldFont = None
            dc.SetPen( wx.BLACK_PEN)
            dc.SetBrush( wx.BLACK_BRUSH)
            if object.type == 'line':
                if 'fill' in object.options:
                    #oldPen = dc.GetPen()
                    width = 1
                    if 'width' in object.options:
                        width = object.options['width']
                    dc.SetPen(wx.Pen(object.options['fill'], width))
                    #print "created new pen for line with color:",object.options['fill']
                #else: print "using black color"
                dc.DrawLine( x1, y1, x2, y2)
            elif object.type == 'oval':
                if 'outline' in object.options:
                    #oldPen = dc.GetPen()
                    width = 1
                    if 'width' in object.options:
                        width = object.options['width']
                    dc.SetPen(wx.Pen(object.options['outline'], width))
                #oldBrush = dc.GetBrush()
                if 'fill' in object.options:
                    dc.SetBrush(wx.Brush(object.options['fill']))
                else:
                    dc.SetBrush(wx.TRANSPARENT_BRUSH)
                dc.DrawEllipse( x1, y1, w, h)
            elif object.type == 'text':
                if 'font' in object.options:
                    font = wx.Font(object.options['font'][1], wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL, faceName = object.options['font'][0])
                    oldFont = dc.GetFont()
                    dc.SetFont(font)
                if 'fill' in object.options:
                    dc.SetTextForeground(object.options['fill'])
                #compute text size in order to respect the anchor indication
                text = str(object.options['text'])
                width, height, line_height = dc.GetMultiLineTextExtent(text)
                if 'anchor' in object.options and object.options['anchor']:
                    if 's' in object.options['anchor']:
                        y1 = y1 - height
                    if 'e' in object.options['anchor']:
                        x1 = x1 - width
                if 'justify' in object.options:
                    x1 = x1 - width/2
                dc.DrawText( text, x1, y1)
                if 'fill' in object.options:
                    dc.SetTextForeground('black')
##            if oldPen:
##                dc.SetPen(oldPen)
##            if oldBrush:
##                dc.SetBrush(oldBrush)
            if oldFont:
                dc.SetFont(oldFont)

    def OnSize(self):
        # should reposition all items as the center changed
        self.width,self.height = self.canvas.GetClientSize()
        # print "client width=%d height=%d" % (w,h)
        new_cx = self.width/2
        new_cy = self.height/2
        self.dcx = new_cx - host.cx
        self.dcy = new_cy - host.cy
        # print "modified dcx=%d dcy=%d" % (self.dcx, self.dcy)
        # should redraw here?        
        #self.OnPaint()
        
    def find_overlapping( self, x1, y1, x2, y2):
        # should return a list of all object under mouse
        selected = []
        cursor_rect = wx.Rect(x1, y1, x2-x1, y2-y1)
        for object in self.objects:
            if not object.isHoverable:
                continue
            if object.type == 'line': pass
            elif object.type == 'oval': 
                if self.intersect_rects( cursor_rect, wx.Rect(object.options['x1']+self.dcx, object.options['y1']+self.dcy, object.options['x2']-object.options['x1'], object.options['y2']-object.options['y1'])): 
                    selected.append(object)
            elif object.type == 'text': pass
        return selected
    
    def intersect_rects( self, r1, r2):
        return not ( r2.x > r1.x+r1.width
            or r2.x+r2.width < r1.x
            or r2.y > r1.y+r1.height
            or r2.y+r2.height < r1.y )

    def itemconfig(self, object, opts = {}):
        for option,val in opts.iteritems():
            object.options[option] = val

class MyCanvasObject:
    
    def __init__ (self, manager, type=None, opts={} ):
        self.manager = manager
        self.type = type
        self.isHoverable = True # indicates that this should be considered for selection when hovering with the mouse
        self.isRelativePosX = self.isRelativePosY = True # indicates that it's position is relative to the center of the drawing
        # otherwise is relative to one of the margins by using the sign of x1 and y1 to indicate the margin:
        # +, + is left, top corner
        # +, - is left, bottom corner
        # -, + is right, top corner
        # -, - is right, bottom
        # and the value of x1 and y1 is used to relatively position to the determined corner
        self.options = opts
        self.def_options = { 'x1':0, 'x2':0, 'y1':0, 'y2':0, 'text':''}
        for option,def_val in self.def_options.iteritems():
            if not option in self.options:
                self.options[option]=def_val
        
    def lower(self):
        self.manager.lower(self)
        
    def lift(self):
        self.manager.lift(self)
               
    def setRelative2Center( self, *args, **kw):
        if len(kw) ==0:
            if len(args)==1:
                self.isRelativePosX = self.isRelativePosY = args[0]
            elif len(args)>1:
                self.isRelativePosX = args[0]
                self.isRelativePosY = args[1]
        else:
            if 'relative_x' in kw:
                self.isRelativePosX = kw['relative_x']
            elif len(args)>0:
                self.isRelativePosX = args[0]
            if 'relative_y' in kw:
                self.isRelativePosY = kw['relative_y']
            elif len(args)>0:
                self.isRelativePosY = args[0]
        

    def coords( self, list):
        count = len(list)
        if count>0:
            self.manager.itemconfig( self, {'x1':list[0][0], 'y1':list[0][1]})
        if count>1:
            self.manager.itemconfig( self, { 'x2':list[1][0], 'y2':list[1][1]})
        
    def delete(self):
        self.manager.remove(self)
        
    def config(self, *args, **kw):
        self.manager.itemconfig( self, kw)
    
if __name__ == "__main__":
    dc_objects = CanvasObjects(object())
    text_obj = dc_objects.Text({'text':'alegorie', 'x1':12, 'x2':4})
    print "object of type %s has options %s" % ( text_obj.type, str(text_obj.options) )
    dc_objects.lower(object())