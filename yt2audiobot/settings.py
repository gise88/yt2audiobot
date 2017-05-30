#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import os


BOT_NAME = 'yt2audiobot'

# repository github
URL_REPO_GITHUB = 'https://github.com/gise88/yt2audiobot'


# auto ban user after an amount of requested access
REQUESTED_ACCESS_FOR_BAN = 5


# in this folder will be created the sqlite databases and the output directory for the audio files
WORKING_DIRECTORY_ABS_PATH = os.path.abspath('.')
SECRETS_FILE_NAME = 'SECRETS.txt'
USERS_DB_NAME = 'yt2audiobot_users.sqlite'
AUDIO_DB_NAME = 'yt2audiobot_audio.sqlite'
AUDIO_OUTPUT_DIR_NAME = 'output_dir'
PREFERRED_AUDIO_CODEC = 'mp3'
LIMIT_VIDEO_DURATION = 60 * 30


# paths
SECRETS_PATH = os.path.join(WORKING_DIRECTORY_ABS_PATH, SECRETS_FILE_NAME)
AUDIO_OUTPUT_DIR = os.path.join(WORKING_DIRECTORY_ABS_PATH, AUDIO_OUTPUT_DIR_NAME)


# ythelper settings
OUTPUT_FORMAT = os.path.join(AUDIO_OUTPUT_DIR, '%(id)s.%(ext)s')


# dbmanagers settings
ABS_PATH_USERS_DB = os.path.join(WORKING_DIRECTORY_ABS_PATH, USERS_DB_NAME)
ABS_PATH_AUDIO_DB = os.path.join(WORKING_DIRECTORY_ABS_PATH, AUDIO_DB_NAME)


# spotifyhelper settings
BAD_WORDS = [
    '[', ']', '(', ')',
    'ft', 'feat',
    'Official', 'Music', 'Video'
]


# secrets
BOT_SECRETS = {
    'yt2audiobot_root': '',
    'telegram_token': '',
    'musixmatch_key': '',
    'spotify_client_id': '',
    'spotify_client_secret': '',
}
