#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals, absolute_import

import logging
import requests
from datetime import datetime
from telebot.types import JsonDeserializable


from yt2audiobot import settings


logger = logging.getLogger(settings.BOT_NAME)

# https://developer.musixmatch.com/buyer/stats
# https://developer.musixmatch.com/documentation/api-reference/track-search


class Header(JsonDeserializable):
    @classmethod
    def de_json(cls, json_string):
        obj = cls.check_json(json_string)
        status_code = obj['status_code']
        execute_time = obj['execute_time']
        available = obj['available']
        return cls(status_code, execute_time, available)
    
    
    def __init__(self, status_code, execute_time, available):
        self.status_code = status_code
        self.execute_time = execute_time
        self.available = available


class Track(JsonDeserializable):
    keys = [
        'track_id',
        'track_mbid',
        'track_isrc',
        'track_spotify_id',
        'track_soundcloud_id',
        'track_xboxmusic_id',
        'track_name',
        'track_rating',
        'track_length',
        'commontrack_id',
        'instrumental',
        'explicit',
        'has_lyrics',
        'has_subtitles',
        'num_favourite',
        'lyrics_id',
        'subtitle_id',
        'album_id',
        'album_name',
        'artist_id',
        'artist_mbid',
        'artist_name',
        'album_coverart_100x100',
        'album_coverart_350x350',
        'album_coverart_500x500',
        'album_coverart_800x800',
        'track_share_url',
        'track_edit_url',
        'commontrack_vanity_id',
        'restricted',
        'first_release_date',
        'updated_time',
        'primary_genres',
        'secondary_genres'
    ]
    
    
    @classmethod
    def de_json(cls, json_string):
        obj = cls.check_json(json_string)
        opts = { }
        for key in Track.keys:
            if key in obj:
                opts[key] = obj[key]
        return cls(opts)
    
    
    @classmethod
    def parse_track_list(cls, track_list):
        ret = []
        for t in track_list:
            ret.append(Track.de_json(t['track']))
        return ret
    
    
    def __init__(self, options):
        for key in Track.keys:
            if key in options:
                setattr(self, key, options[key])
            else:
                setattr(self, key, None)
        try:
            self.first_release_date = datetime.strptime(self.first_release_date, '%Y-%m-%dT%H:%M:%SZ')
        except ValueError as e:
            if self.first_release_date != '':
                logger.error(e)
            self.first_release_date = None


class Message(JsonDeserializable):
    @classmethod
    def de_json(cls, json_string):
        obj = cls.check_json(json_string)
        header = Header.de_json(obj['message']['header'])
        body = obj['message']['body']
        opts = { }
        if 'track_list' in body:
            opts['track_list'] = Track.parse_track_list(body['track_list'])
        return cls(header, opts)
    
    
    def __init__(self, header, options):
        self.header = header
        self.track_list = None
        for key in options:
            setattr(self, key, options[key])


def __do_mxm_request(method, data):
    MUSIXMATCH_URL = 'http://api.musixmatch.com/ws/1.1/'
    data['apikey'] = settings.BOT_SECRETS['musixmatch_key']
    data['format'] = 'json'
    result = requests.get(MUSIXMATCH_URL + method, params=data)
    return Message.de_json(result.text.encode('ascii', 'ignore'))


def track_search(title):
    req = {
        'q': title,
        's_track_rating': 'desc'
    }
    return __do_mxm_request('track.search', req)
