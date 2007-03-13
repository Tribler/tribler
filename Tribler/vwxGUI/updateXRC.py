import sys, re, os


def changeFile(filename):
    f_in = file(filename, 'r')
    data = f_in.read()
    f_in.close()
    
    olddata = data
    
    # Define all used custom classes here and the related wxPython classes. They will be replaced by the regexp.
    # (customClassName, wxClassName, filename for import)
    customDir = 'Tribler.vwxGUI.'
    customClasses = [('bgPanel', 'wxPanel', customDir+'bgPanel'), 
                     ('tribler_topButton', 'wxPanel', customDir+'tribler_topButton'),
                     ('standardOverview', 'wxPanel', customDir+'standardOverview'), 
                     ('torrentItem', 'wxPanel', customDir+'torrentItem'),
                     ('standardDetails', 'wxPanel', customDir+'standardDetails'),
                     ('torrentFilter', 'wxPanel', customDir+'torrentFilter'),
                     ('torrentTabs', 'wxPanel', customDir+'torrentTabs'), 
                     ('statusDownloads', 'wxPanel', customDir+'statusDownloads'),
                     ('torrentGrid', 'wxPanel', customDir+'torrentGrid'),
                     ('standardStatus', 'wxPanel', customDir+'standardStatus'),
                     ('wxFrame', 'wxFrame', 'abc_vwx')]
    
    
    
    for (customClass, wxClass, customFile) in customClasses:
        data = re.sub('<object class="%s" name="(.*?)">' % customClass, u'<object class="%s" name="\\1" subclass="%s.%s">' % (wxClass, customFile, customClass), data )
    
    data = re.sub('<bg>0</bg>', u'<bg>#000000</bg>', data)
    if data != olddata:
        # save file)
        f_bak = file(filename+'.old', 'w')
        f_bak.write(olddata)
        f_bak.close()
        
        f_out = file(filename, 'w')
        f_out.write(data)
        f_out.close()
        return 'changed'
    return 'no changes'
    
def main(args):
    # find all xrc files in this dir
    xrcs = []
    for filename in os.listdir('.'):
        if filename.lower().endswith('.xrc'):
            xrcs.append(filename)
        
    print 'Found %d xrc files in the current directory:' % len(xrcs)
    
    for filename in xrcs:
        print '\t%s (%s)' % (filename, changeFile(filename))
        

    print 'Updated xrc files and wrote backup files (.old) if changed.'





if __name__ == '__main__':
    main(sys.argv)