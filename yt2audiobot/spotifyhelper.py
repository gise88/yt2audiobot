#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import spotipy
import settings
from spotipy.oauth2 import SpotifyClientCredentials


class Spotify(object):
    
    client_credentials_manager = None
    sp = None
    
    @classmethod
    def authenticate(cls):
        cls.client_credentials_manager = SpotifyClientCredentials(
            client_id=settings.BOT_SECRETS['spotify_client_id'],
            client_secret=settings.BOT_SECRETS['spotify_client_secret']
        )
        cls.sp = spotipy.Spotify(client_credentials_manager=cls.client_credentials_manager)


    @classmethod
    def search(cls, query):
        
        results = cls.sp.search(q=query, limit=10)
        data = []
        for t in results['tracks']['items']:
            artists = []
            for a in t['artists']:
                artists.append(a['name'])
            data.append({
                'title': t['name'],
                'artists': artists,
                'album': t['album']['name'],
                'track_number': t['track_number']
            })
        return data


    @classmethod
    def request_track(cls, track_id):
        urn = 'spotify:track:' + track_id
        return cls.sp.track(urn)
