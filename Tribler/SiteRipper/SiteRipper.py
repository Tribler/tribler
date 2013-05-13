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
    fileName = __getFileName(url)
    injector.saveWebPageFile(fileName)
    #Seed file
    file = os.path.abspath(''.join([fileName,'.html']))
    seedFile(file)
    
def __getFileName(url):
    '''Get the appropiate filename by using the given url
    Args:
        url (str): The url to be used  to creat the filename.'''
    #Remove http://www.
    result = url
    if result.startswith("http://"):
        result = result[7:]
    if result.startswith('www.'):
        result = result[4:]
    #Replace all / with -
    result = ['_' if x=='/' else x for x in result]
    #Return
    return ''.join(result)