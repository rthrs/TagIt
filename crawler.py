# -*- coding: utf-8 -*-
## @package crawler
#  Web crawler that retrieves music content from given source, analyzes it and
#  adds songs with proper tags into TagIt! database unless they currently exist.
#
#  Supported sites: tekstowo.pl, youtube.com
#
#  Title tag convention: New word always starts with capital letter
#
#  For more usage details run crawler.py with -h option.
##
"""
Web crawler that retrieves music content from given source, analyzes it and
adds songs with proper tags into TagIt! database unless they currently exist.

Supported sites: tekstowo.pl, youtube.com
Title tag convention: New word always starts with capital letter

Source options:
    --tekstowo-song=[url]       crawl data from [url] which starts with
                                tekstowo.pl/piosenka
    --tekstowo-artist=[url]     crawl data from [url] which starts with
                                tekstowo.pl/piosenki_artysty
    --tekstowo-letter=[letter]  crawl data from tekstowo.pl/artysci_na,[letter].html
                                [letter] could be also named as 'pozostale'
    --tekstowo-all              crawl entire tekstowo.pl

Additional options:
    -s  save downloaded audio files (in /home/[user])
"""
from __future__ import unicode_literals
from os.path import expanduser
from termcolor import colored
from lxml import html
from add import addSong
from recognize import recognize
import sys
import os
import getopt
import youtube_dl
import urllib2
import re
import string

ERROR_STR = '\033[31mERROR:\033[0m '

def html_dl(url):
    """
        Download HTML source code from given url.
        Args:
            url: url to page for download
    """
    return urllib2.urlopen(url).read()


def tesktowo_tags(source):
    """
        Retrieve proper songs tags from tesktowo.pl page source.
        Args:
            source: tekstowo.pl HTML source string
        Returns:
            dictionary with metadata containing tags like
            'artist', 'title', 'album' and 'year'
    """
    tree = html.fromstring(source)
    artist = tree.xpath('//*[@id="center"]/div[1]/a[3]/text()')
    title = tree.xpath('//*[@id="center"]/div[1]/a[4]/text()')
    yreg = re.compile(r'Rok powstania:</th><td><p>([0-9]+)').search(source)
    areg = re.compile(r'yty:</th><td><p>([^<]+)').search(source)
    year, album = None, None
    if areg is not None:
        album = areg.group(1)
    if yreg is not None:
        year = yreg.group(1)
    if not artist or not title:
        raise Exception(ERROR_STR + '[crawler] cannot parse artist and title')
    tags = {
        'artist': artist[0],
        'title': title[0],
        'album': album,
        'year': year
    }
    print "[crawler] parsed tags: artist='%s'title='%s' album='%s' year='%s'" % (artist[0], title[0], album, year)
    return tags


def tekstowo_youtube_url(source):
    """
        Retrieve youtube link to song from tekstowo.pl page source.
        Args:
            source: tekstowo.pl HTML source string
        Returns:
            youtube url to song from given page
    """
    reg = re.compile(r"var videoID = \"(.*)\";")
    try:
        video_id = reg.search(source).group(1)
    except Exception:
        raise Exception(ERROR_STR + '[crawler] cannot find videoID')
    if not video_id:
        raise Exception(ERROR_STR + '[crawler] empty videoID')

    return "https://www.youtube.com/watch?v=" + video_id


def youtube_dl_mp3(url, directory=expanduser('~/')):
    """
        Download audio from given youtube video url.
        Args:
            url: youtube video url
            directory: path to download folder
        Returns:
            dictionary with 'path' to downloaded song and 'title' of
            given youtube video
    """
    outtmpl = directory + '%(id)s.%(ext)s'
    options = {
        'format': 'bestaudio/best', # choice of quality
        'extractaudio' : True,      # only keep the audio
        'audioformat' : "mp3",      # convert to mp3
        'outtmpl': outtmpl,         # name the file the title of the video
        'noplaylist' : True,        # only download single song, not playlist
    }

    ydl  = youtube_dl.YoutubeDL(options)
    ydl.download([url])
    info = ydl.extract_info(url, download=False)

    path = directory + info['id'] + '.' + info['ext']
    print '[crawler] path to downloaded audio: %s' % path
    return {
        'path': path,
        'title': info['title']
    }


def remove_file(path, save):
    """
        Remove file if save option is set to True
        Args:
            path: path to a file for possible removal
            save: if set to true, remove given file, do nothing otherwise
    """
    if not save:
        os.remove(path)
        print "[crawler] removing audio file..."


def tekstowo_song(url, save):
    """
        Crawl music content from given tekstowo.pl url to singel song and
        add it to the database unless it's already in it or some errors occured.
        Args:
            url: tesktowo.pl url for single file
            save: choose if save downloaded song or remove it after
                  correct addition to database
    """
    print '[crawler] processing tekstowo_song({}, {})'.format(url, save)
    source = html_dl(url)
    try :
        tags = tesktowo_tags(source)
        yt_url = tekstowo_youtube_url(source)
        ret = youtube_dl_mp3(yt_url)
    except Exception, e:
        print e
        print colored("[crawler] processing TERMINATED", "red")
        return
    if recognize(ret['path']) != -1:
        remove_file(ret['path'], save)
        print colored('[crawler] song already in database', 'yellow')
        return

    print '[crawler] adding song into database...'
    err = addSong(ret['path'], tags)
    remove_file(ret['path'], save)
    if  err != 1:
        print '[crawler] ERROR: while adding song [addSong() errno: %d]' % err
        return
    print colored('[crawler] SUCCESS: song added into database', 'green')


def page_iterator(url, save, fun):
    """
        Iterate through links from tekstowo.pl url which conatins list of
        either artists with given letter or specific artists songs.
        Args:
            url: tesktowo.pl url
            save: choose if save downloaded song or remove it after
                  correct addition to database
            fun: function handler for collected links
    """
    tekstowo_url = 'http://www.tekstowo.pl'
    while True:
        source = html_dl(url)
        tree = html.fromstring(source)
        links = tree.xpath(u"//div[@class='content']//a[@class='title']")
        for l in links:
            fun(tekstowo_url + l.attrib['href'], save)

        next_page = tree.xpath(u"//a[@title='Następna >>']")
        if not next_page:
            break
        url = tekstowo_url + next[0].attrib['href']


def tekstowo_artist(url, save):
    """
        Crawl data from tekstowo.pl url to list of specific artists songs.
        Args:
            url: tesktowo.pl url to artists songs page
            save: choose if save downloaded songs after correct
                  addition to database
    """
    page_iterator(url, save, tekstowo_song)


def tekstowo_letter(letter, save):
    """
        Crawl data from tekstowo.pl url to list of artists with given letter.
        Args:
            url: tesktowo.pl url to list of artists with given letter
            save: choose if save downloaded songs after correct
                  addition to database
    """
    url = 'http://www.tekstowo.pl/artysci_na,{}.html'.format(letter)
    page_iterator(url, save, tekstowo_artist)


def tekstowo_all(save):
    """
        Crawl entire tekstowo.pl.
        Args:
            save: choose if save downloaded songs after correct
                  addition to database
    """
    for l in string.ascii_uppercase:
        tekstowo_letter(l, save)
    tekstowo_letter('pozostale', save)


def main():
    """
        Main function.
    """
    long_opt = [
        "help",
        "tekstowo-song=",
        "tekstowo-artist=",
        "tekstowo-all",
        "tekstowo-letter=",
        "tekstowo-all"
    ]

    # parsing options
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hs", long_opt)
    except getopt.error, msg:
        print msg
        print "For help use --help"
        sys.exit(2)

    save = ('-s', '') in opts

    # handling options
    for o, a in opts:
        if o in ["-h", "--help"]:
            print __doc__
            sys.exit(0)
        if o in ["--tekstowo-song"]:
            tekstowo_song(a, save)
        if o in ["--tekstowo-artist"]:
            tekstowo_artist(a, save)
        if o in ["--tekstowo-letter"]:
            tekstowo_letter(a, save)
        if o in ["--tekstowo-all"]:
            tekstowo_all(save)

    sys.exit(0)


if __name__ == "__main__":
    main()
