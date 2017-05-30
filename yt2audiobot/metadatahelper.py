#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals, absolute_import

import re

from mutagen.mp3 import MP3, EasyMP3
from mutagen.id3 import error, PictureType
from mutagen.id3._frames import APIC

from yt2audiobot import utils
from yt2audiobot import settings
from yt2audiobot import musixmatch
from yt2audiobot.spotifyhelper import Spotify


class SongMetadata(object):
    keys = [
        'title',
        'author',
        'album',
        'track_number',
        'first_release_date'
    ]
    
    
    def __init__(self, data):
        self.__repr__ = self.__str__
        for key in SongMetadata.keys:
            if key in data:
                setattr(self, key, data[key])
            else:
                setattr(self, key, None)
        if self.track_number is None:
            self.track_number = 0
    
    
    def __str__(self, printalbum=True):
        text = ''
        if self.author is not None:
            text = self.author + ' - '
        text = text + self.title
        if self.first_release_date is not None:
            text = text + ' (' + str(self.first_release_date.year) + ')'
        if printalbum and self.album is not None:
            text = text + ', ' + self.album
        return text
    
    
    def to_filename(self):
        return utils.get_valid_filename(self.__str__(printalbum=False))


def remove_bad_word(text):
    for word in settings.BAD_WORDS:
        text = text.replace(word, '')
    return text


# thanks to: http://stackoverflow.com/a/5320179
def find_whole_word(w, text):
    return re.compile(r'\b({0})\b'.format(w), flags=re.IGNORECASE).search(text)


def search_in_text(word_list, text):
    for w in word_list:
        if find_whole_word(w, text):
            return True
    return False


def metadata_from_title(orig_title):
    # remove substing inside parenthesis..
    title = re.sub('\(.*?\)', '', orig_title)
    title = re.sub('\[.*?\]', '', title)
    title = remove_bad_word(title)
    
    title_words = title.split(' ')
    try:
        title_words.remove('')
    except Exception as e:
        pass
    
    result = musixmatch.track_search(title)
    for r in result.track_list:
        if r.track_rating > 75:
            if search_in_text(title_words, r.track_name) and search_in_text(title_words, r.artist_name):
                track_number = 0
                if r.track_spotify_id:
                    try:
                        track_number = Spotify.request_track(r.track_spotify_id)['track_number']
                    except:
                        pass
                    data = {
                        'title': r.track_name,
                        'author': r.artist_name,
                        'album': r.album_name,
                        'track_number': track_number,
                        'first_release_date': r.first_release_date
                    }
                    return SongMetadata(data)
    
    results = Spotify.search(title)
    for r in results:
        if search_in_text(title_words, r['title']) and search_in_text(title_words, ' '.join(r['artists'])):
            data = {
                'title': r['title'],
                'author': ' - '.join(r['artists']),
                'album': r['album'],
                'track_number': r['track_number']
            }
            return SongMetadata(data)
    data = {
        'title': orig_title
    }
    return SongMetadata(data)


def write_metadata(metadata, mp3_file, thumbnail):
    audiofile = EasyMP3(mp3_file)
    try:
        audiofile.add_tags()
    except error:
        pass
    
    audiofile['title'] = metadata.title
    if metadata.author:
        audiofile['artist'] = metadata.author
    if metadata.album:
        audiofile['album'] = metadata.album
    if metadata.track_number != 0:
        audiofile['tracknumber'] = str(metadata.track_number)
    if metadata.first_release_date:
        audiofile['date'] = str(metadata.first_release_date)
    audiofile.save()
    
    if thumbnail is not None:
        audiofile = MP3(mp3_file)
        audiofile.tags.add(APIC(encoding=3,
                                mime=thumbnail.mimetype,
                                type=PictureType.COVER_FRONT,
                                desc=u'Cover Front',
                                data=open(thumbnail.filename).read()))
    audiofile.save()
