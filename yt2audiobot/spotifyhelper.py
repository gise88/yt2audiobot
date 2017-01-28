#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals

import spotipy


sp = spotipy.Spotify()


def search_in_spotify(query):
    results = sp.search(q=query, limit=10)
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


def request_track(track_id):
    urn = 'spotify:track:' + track_id
    return sp.track(urn)
