#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import logging
from peewee import *

from yt2audiobot import settings


logger = logging.getLogger(settings.BOT_NAME)

audio_db = SqliteDatabase(settings.ABS_PATH_AUDIO_DB)


class CannotAddEntryException(Exception):
    def __init__(self, message):
        super(CannotAddEntryException, self).__init__(message)


class YoutubeToTelegramFile(Model):
    youtube_id = CharField(primary_key=True)
    telegram_file_id = CharField()
    downloaded_times = IntegerField(default=1)
    
    class Meta:
        database = audio_db


class AudioMetadata(Model):
    mapping = ForeignKeyField(YoutubeToTelegramFile, primary_key=True)
    title = CharField(default='')
    author = CharField(null=True)
    album = CharField(null=True)
    track_number = IntegerField(default=0)
    first_release_date = DateField(null=True)
    file_size = IntegerField(default=0)
    duration = IntegerField(default=0)
    
    class Meta:
        database = audio_db


class AudioDBController(object):
    def __init__(self):
        self.db = audio_db
        self.db.connect()
        self.db.create_tables([YoutubeToTelegramFile, AudioMetadata], safe=True)
    
    
    def __predicate_youtube_and_telegram_file(self, youtube_id=None, telegram_file_id=None):
        if youtube_id is None and telegram_file_id is None:
            raise Exception('youtube_id and telegram_file_id are None!')
        youtube_id_predicate = (YoutubeToTelegramFile.youtube_id == youtube_id)
        telegram_file_id_predicate = (YoutubeToTelegramFile.telegram_file_id == telegram_file_id)
        return (youtube_id_predicate) | (telegram_file_id_predicate)
    
    
    def __youtube_telegram_select_query(self, **attributes):
        youtube_id = attributes.get('youtube_id', None)
        telegram_file_id = attributes.get('telegram_file_id', None)
        predicate = self.__predicate_youtube_and_telegram_file(youtube_id=youtube_id, telegram_file_id=telegram_file_id)
        return YoutubeToTelegramFile.select().where(predicate)
    
    
    def search_by_youtube_or_telegram_file(self, **attributes):
        entry = None
        try:
            entry = self.__youtube_telegram_select_query(**attributes).get()
            return (entry, AudioMetadata.select()
                    .join(YoutubeToTelegramFile).where(AudioMetadata.mapping == entry).get())
        except YoutubeToTelegramFile.DoesNotExist:
            return (None, None)
        except AudioMetadata.DoesNotExist:
            return (entry, None)
    
    
    def __add_youtube_telegram_file(self, **attributes):
        youtube_id = attributes.get('youtube_id', None)
        if youtube_id is None:
            raise CannotAddEntryException('youtube_id == None')
        telegram_file_id = attributes.get('telegram_file_id', None)
        if telegram_file_id is None:
            raise CannotAddEntryException('telegram_file_id == None')
        return YoutubeToTelegramFile.create(youtube_id=youtube_id, telegram_file_id=telegram_file_id)
    
    
    def __add_metadata_to_entry(self, mapping, **attributes):
        logger.info('__add_metadata_to_entry: %s', attributes['youtube_id'])
        title = attributes.get('title', None)
        if title is None:
            raise Exception('Title is None: ' + attributes['youtube_id'])
        
        AudioMetadata.create(
            mapping=mapping,
            title=title,
            author=attributes.get('author', None),
            album=attributes.get('album', None),
            track_number=attributes.get('track_number', 0),
            first_release_date=attributes.get('first_release_date', None),
            file_size=attributes.get('file_size', 0),
            duration=attributes.get('duration', 0),
        )
    
    
    def add_youtube_telegram_file_entry_and_metadata(self, **attributes):
        try:
            yt2tgmapping, audiometadata = self.search_by_youtube_or_telegram_file(**attributes)
            if yt2tgmapping is None:
                yt2tgmapping = self.__add_youtube_telegram_file(**attributes)
            if audiometadata is None:
                self.__add_metadata_to_entry(yt2tgmapping, **attributes)
        except CannotAddEntryException as e:
            raise CannotAddEntryException(str(e) + ' - title: ' + str(attributes['title']))
