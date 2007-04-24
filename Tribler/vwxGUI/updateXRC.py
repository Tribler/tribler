import sys, re, os, os.path


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
                     ('tribler_List', 'wxListCtrl', customDir+'tribler_List'),                     
                     ('FilesList', 'wxListCtrl', customDir+'tribler_List'),                     
                     ('btn_DetailsHeader', 'wxPanel', customDir+'btn_DetailsHeader'),
                     ('statusDownloads', 'wxPanel', customDir+'statusDownloads'),
                     ('standardOverview', 'wxPanel', customDir+'standardOverview'), 
                     ('standardDetails', 'wxPanel', customDir+'standardDetails'),                     
                     ('standardPager', 'wxPanel', customDir+'standardPager'),
                     
                     ('filesOverview', 'wxPanel', customDir+'filesOverview'),                     
                     ('filesFilter', 'wxPanel', customDir+'filesFilter'),
                     ('filesItem', 'wxPanel', customDir+'filesItem'),    
                     ('filesTabs', 'wxPanel', customDir+'filesTabs'), 
                     ('filesDetails', 'wxPanel', customDir+'filesDetails'), 
                     ('filesGrid', 'wxPanel', customDir+'standardGrid'),
                     
                     ('personsOverview', 'wxPanel', customDir+'personsOverview'),
                     ('personsFilter', 'wxPanel', customDir+'personsFilter'),                     
                     ('personsGrid', 'wxPanel', customDir+'standardGrid'),
                     ('personsDetails', 'wxPanel', customDir+'personsDetails'),
                      
                     ('libraryGrid', 'wxPanel', customDir+'standardGrid'),
                     ('libraryDetails', 'wxPanel', customDir+'libraryDetails'),
                     
                     ('friendsGrid', 'wxPanel', customDir+'standardGrid'),
                     ('friendsOverview', 'wxPanel', customDir+'friendsOverview'), 
                                         
                     ('subscriptionsOverview', 'wxPanel', customDir+'subscriptionsOverview'),                     
                     ('TasteHeart', 'wxPanel', customDir+'TasteHeart'),
                     ('TextButton', 'wxStaticText', customDir+'TextButton'),
                     ('wxFrame', 'wxFrame', 'abc_vwx')]
    
    
    
    for (customClass, wxClass, customFile) in customClasses:
        data = re.sub('<object class="%s" name="([^"]+)">' % customClass, u'<object class="%s" name="\\1" subclass="%s.%s">' % (wxClass, customFile, customClass), data )
    
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
        
    print 'Found %d xrc files in the current directory:' % len(xrcs)
    
    for filename in xrcs:
        print '\t%s (%s)' % (filename, changeFile(os.path.join(dir,filename)))
        

    print 'Updated xrc files and wrote backup files (.old) if changed.'





if __name__ == '__main__':
    main(sys.argv)