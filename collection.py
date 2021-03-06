## @package collection
#  Functions for creating and adding files to collections.
##

import os
import tag
import eyed3
import sys
import thread
import pickle

from watchdog.observers import Observer
from watchdog.events import FileCreatedEvent, FileSystemEventHandler

reload(sys)
sys.setdefaultencoding('utf-8')

class FileCreatedEventHandler(FileSystemEventHandler):
    """
        Waits for files created in collections.
    """

    def on_created(self, event):
        what = 'directory' if event.is_directory else 'file'
        if what == 'file':
            addToCollection(event.src_path)


def addToCollection(filePath):
    """
        Adds file to collection it's currently in.
    """
    f = tag.tagFile(filePath, True)
    folder = os.path.split(filePath)[0]
    if folder[-1:] != "/":
        folder += "/"

    if f == -1: # didn't tag file
        if not os.path.isdir(folder+"unknown"):
            os.mkdir(folder+"unknown")
        os.rename(filePath, folder+"unknown/"+os.path.split(filePath)[1])
        return -1

    artist = eyed3.load(f).tag.artist
    if not os.path.isdir(folder+artist):
        os.mkdir(folder+artist)
    filename = os.path.split(f)[1]
    os.rename(f, folder+artist+"/"+filename)
    return 0


def watchNewFolder(folderPath, save=True):
    """
        Watches new folder for changes.
        Returns:
            -1 if start was not successful
            0 otherwise
    """
    eventHandler = FileCreatedEventHandler()
    observer = Observer()
    observer.schedule(eventHandler, folderPath)
    try:
        observer.start()
    except OSError:
        return -1
    if save:
        configFile = open('watchedFolders', 'a')
        configFile.write(folderPath+"\n")
        configFile.close()
    return 0


def watchFolders():
    """
        Starts to watch all folders in config file.
    """
    configFile = open('watchedFolders', 'r')
    for line in configFile:
        watchNewFolder(line[:-1], False)
    configFile.close()


def moveUp(src, dst):
    """
        Moves all files from src to dst directory.
        Returns:
            -1 if src or dst is not a directory
    """
    if not (os.path.isdir(src) and os.path.isdir(dst)):
        return -1

    if src[-1:] != "/":
        src += "/"

    if dst[-1:] != "/":
        dst += "/"

    for f in os.listdir(src):
        if not os.path.isdir(f):
            os.rename(src+f, dst+src.replace('/', '_')+f)


def moveFiles(path):
    """
        Moves every file from subfolders of path to path.
        Args:
            path: Path to folder.
        Returns:
            -1 if acction was unsuccessful
            1 otherwise
    """
    # TODO: may not work with weird filenames
    if not os.path.isdir(path):
        return -1

    # path is a correct directory
    for d in os.listdir(path):
        newPath = path+"/"+d
        if os.path.isdir(newPath):
            moveFiles(newPath)
            moveUp(newPath, path)
            os.rmdir(newPath)


def createCollection(path, status=None, aborted=[False]):
    """
        Creates collection from a folder.
        Creates a new folder for each artist and copies his music to this folder.
        Moves unrecognized files to "unknown" folder.
        Args:
            path: Path to folder.
        Returns:
            -1, 0, 0 if path is not correct.
            1, list of untagged, list of tagged otherwise.
    """
    if not os.path.isdir(path):
        return -1, 0, 0

    if path[-1:] != "/":
        path += "/"

    moveFiles(path)
    untagged = tag.tagFolder(path, status, aborted)
    if untagged != []:
        os.mkdir(path+"unknown")
    for f in untagged:
        os.rename(path+f, path+"unknown/"+f)

    if aborted[0] == True:
        return -1, 0, 0

    tagged = []
    for f in os.listdir(path):
        if aborted[0] == True:
            return -1, 0, 0
        if not os.path.isdir(path+f):
            tagged.append(path+f)

    prog = 0
    for f in tagged:
        if aborted[0] == True:
            return -1, 0, 0
        artist = eyed3.load(f).tag.artist
        if not os.path.isdir(path+artist):
            os.mkdir(path+artist)
        filename = os.path.split(f)[1]
        os.rename(f, path+artist+"/"+filename)
        prog += 1
        if status is not None:
            status(float(prog) / len(tagged))

    watchNewFolder(path)
    return 1, untagged, tagged
