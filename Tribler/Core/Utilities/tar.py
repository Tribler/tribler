import tarfile
from duplicity.path import PathDeleter

def tarFolder(pathTarget, pathDestination,fileName):
    '''Create a tarfile of a folder. 
    All files and subfolders are added and the structure of the folder is retained.
    Args:
        pathTarget (str): The path to the folder that needs to be tarred.
        pathDestination (str): The path to the destination of the new tarfile. tar.gz will be appended.
        fileName (str): Filename of the tarfile.'''
    tar = tarfile.open(name = ''.join([pathDestination,fileName,'.tar.gz']), mode = 'w:gz')
    #Add the folder to the tarfile. Arcname is empty so the full path to the directory is not added.
    tar.add(pathTarget,arcname = '')
    tar.close()
    return tar

    
def untarFolder(pathTarget, pathDestination, folderName):
    '''untar a tarfile to the Destination
    Args:
        pathTarget (str): path to the Tarfile. 
        pathDestination: path to the place the tar needs to be unpacked to. 
        folderName: folderName in wich the tarfile will be unpacked to.'''
    tar = tarfile.open(pathTarget, mode = 'r:gz')
    tar.extractall(path = ''.join([pathDestination,'/', folderName]))
        