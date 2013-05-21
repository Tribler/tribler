from Tribler.Core.Session import Session 

import os

class NotFoundFile: 
    pagecontent = """<html />
        <head />
            <title />Eternal Copy Not Found!</title />
        </head />
        
        <script language="javascript" />
            function switchToInternet(){
                iurl = window.location.search.replace( "?", "" );
                iurl = iurl.replace(":", "&#58;")
                window.location = "internetmode://" + iurl;
            }
        </script />
        
        <body />
            <h1 />Eternal Copy Not Found!</h1 />
            We are ever so terribly sorry. <br />
            It appears there is no eternal page for the website: <br />
            <script language="javascript" />
                document.write("<blockquote /><font color=0000FF />" + window.location.search.replace( "?", "" ) + "</font /></blockquote />");
            </script />
            
            <button type="button" onclick="switchToInternet();">Try the internet</button>
        </body />
    </html />"""
    
    file_exists = False
    
    @staticmethod
    def getFilenameCreate():
        """Get the location of pagenotfound.html
            Create it if it does not exist
        """
        NotFoundFile.assertFile()
        return NotFoundFile.getFilename()
    
    @staticmethod
    def getFilename():
        """Get the location of pagenotfound.html
        """
        return Session.get_default_state_dir() + "pagenotfound.html"
    
    @staticmethod
    def assertFile():
        """If pagenotfound.html is not found, create it
        """
        if NotFoundFile.file_exists:
            return
        filename = NotFoundFile.getFilename()
        pathname = os.path.dirname(filename)
        if not os.path.isfile(filename):
            try:
                os.makedirs(pathname)
            except OSError,e:
                pass # Folder already exists
            f = open(filename, 'w')
            f.write(NotFoundFile.pagecontent)
            f.close()
            file_exists = True