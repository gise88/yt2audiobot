#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals, absolute_import

import re

from yt2audiobot import utils
from yt2audiobot import settings
from yt2audiobot import musixmatch
from yt2audiobot import spotifyhelper


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
                        track_number = spotifyhelper.request_track(r.track_spotify_id)['track_number']
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
    
    results = spotifyhelper.search_in_spotify(title)
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
