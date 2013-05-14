#!/usr/bin/python2.7
from Tribler.SiteRipper.WebPageInjector import WebPageInjector
from Tribler.SiteRipper.ResourceSeeder import seedFile

import os

def seedWebPage(url, pageSource): 
    '''Seed a webppage.
    Args:
        url (str): The url to the webpage that needs to be seeded.
        pageSource (str): HTML source code of the webpage.'''
        
    #Create a WebpageInjector
    injector = WebPageInjector(url, pageSource)
    #Save the webpage to file
    injector.saveWebPageFile()    
    #Seed file
    file = os.path.abspath(injector.getFileName())
    seedFile(file)
   
