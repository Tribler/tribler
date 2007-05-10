import sys, re, os, os.path

DEBUG = False

def changeFile(filename):
    f_in = file(filename, 'r')
    data = f_in.read()
    f_in.close()
    
    olddata = data
    
    # Define all used custom classes here and the related wxPython classes. They will be replaced by the regexp.
    # (customClassName, wxClassName, filename for import)
    customDir = 'Tribler.vwxGUI.'
    customClasses = [('bgPanel', 'wxPanel', customDir+'bgPanel'), 
                     ('ImagePanel', 'wxPanel', customDir+'bgPanel'),
                     ('tribler_topButton', 'wxPanel', customDir+'tribler_topButton'),                     
                     ('SwitchButton', 'wxPanel', customDir+'tribler_topButton'),                     
                     ('tribler_List', 'wxListCtrl', customDir+'tribler_List'),                     
                     ('DLFilesList', 'wxListCtrl', customDir+'tribler_List'),                     
                     ('FilesList', 'wxListCtrl', customDir+'tribler_List'),                     
                     ('btn_DetailsHeader', 'wxPanel', customDir+'btn_DetailsHeader'),
                     ('statusDownloads', 'wxPanel', customDir+'statusDownloads'),
                     ('standardOverview', 'wxPanel', customDir+'standardOverview'), 
                     ('standardDetails', 'wxPanel', customDir+'standardDetails'),                     
                     ('standardPager', 'wxPanel', customDir+'standardPager'),
                     ('SwitchButton', 'wxPanel', customDir+'tribler_topButton'),
                     
                     ('filesFilter', 'wxPanel', customDir+'standardFilter'),
                     ('filesDetails', 'wxPanel', customDir+'filesDetails'), 
                     ('filesGrid', 'wxPanel', customDir+'standardGrid'),
                     
                     ('personsFilter', 'wxPanel', customDir+'standardFilter'),                     
                     ('personsDetails', 'wxPanel', customDir+'personsDetails'),
                     ('personsGrid', 'wxPanel', customDir+'standardGrid'),
                      
                     ('libraryGrid', 'wxPanel', customDir+'standardGrid'),
                     ('libraryFilter', 'wxPanel', customDir+'standardFilter'),
                     ('libraryDetails', 'wxPanel', customDir+'libraryDetails'),
                     
                     #('profileOverview', 'wxPanel', customDir+'ProfileOverviewPanel'),
                     ('SmallPerfBar', 'wxPanel', customDir+'perfBar'),                   
                     ('BigPerfBar', 'wxPanel', customDir+'perfBar'),                   
                     ('TriblerLevel', 'wxPanel', customDir+'perfBar'),                   
                     ('profileDetails', 'wxPanel', customDir+'profileDetails'),
                     
                     ('friendsGrid', 'wxPanel', customDir+'standardGrid'),
                     ('friendsFilter', 'wxPanel', customDir+'standardFilter'), 
                                         
                     ('subscriptionsOverview', 'wxPanel', customDir+'subscriptionsOverview'),                     
                     ('subscriptionsDetails', 'wxPanel', customDir+'subscriptionsDetails'),                     
                     ('subscriptionsGrid', 'wxPanel', customDir+'standardGrid'),
                     
                     ('TasteHeart', 'wxPanel', customDir+'TasteHeart'),
                     ('TextButton', 'wxStaticText', customDir+'TextButton')
                     ]
    
    # Define all used custom classes here and the related wxPython classes. They will be replaced by the regexp.
    # (objectName, subClassName)
    customSubClasses = [('profileOverview', customDir+'profileOverviewPanel.ProfileOverviewPanel'),
                        ('MyFrame', 'tribler.ABCFrame')] # no customDir, abc_vwx.py is in root dir
    
    
    for (customClass, wxClass, customFile) in customClasses:
        data = re.sub('<object class="%s" name="([^"]+)">' % customClass, u'<object class="%s" name="\\1" subclass="%s.%s">' % (wxClass, customFile, customClass), data )
    
    for (objectName, subClass) in customSubClasses:
        data = re.sub('<object class="([^"]+)" name="%s">' % objectName, u'<object class="\\1" name="%s" subclass="%s">' % (objectName, subClass), data )
    
    data = re.sub('<bg>\d</bg>', u'<bg>#000000</bg>', data)
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
    try:
        dir = args[0]
    except:
        dir = '.'
    xrcs = []
    for filename in os.listdir(dir):
        if filename.lower().endswith('.xrc'):
            xrcs.append(filename)
        
    if DEBUG:
        print 'updateXRC: Found %d xrc files in the current directory:' % len(xrcs)
    
    for filename in xrcs:
        isChanged = changeFile(os.path.join(dir,filename))
        if DEBUG:
            print '\t%s (%s)' % (filename, isChanged)
        

    if DEBUG:
        print 'Updated xrc files and wrote backup files (.old) if changed.'





if __name__ == '__main__':
    main(sys.argv)