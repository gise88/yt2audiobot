#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import logging
import datetime
from playhouse.migrate import *

from yt2audiobot import settings
from .base import BaseModel
from .usersutils import DEFAULT_TELEGRAM_ID
from .usersutils import UserAlreadyException


logger = logging.getLogger(settings.BOT_NAME)


class AuthorizedUser(BaseModel):
    telegram_id = IntegerField(default=DEFAULT_TELEGRAM_ID, unique=True)
    first_name = CharField(default='')
    last_name = CharField(default='')
    username = CharField(default='', unique=True)
    last_connection = DateField(default=datetime.datetime.now())
    blocked = BooleanField(default=False)
    access_requested_count = IntegerField(default=0)
    
    
    def __repr__(self):
        return '<AuthorizedUser: ' \
               '[{s.telegram_id!r}] ' \
               '{s.first_name!r} ' \
               '{s.last_name!r} ' \
               '{s.username!r}>'.format(s=self)
    
    
    def __str__(self):
        return '[{s.telegram_id}] ' \
               '{s.first_name} ' \
               '{s.last_name} ' \
               '{username}'.format(s=self, username=self.get_username())
    
    
    def delete_instance(self, recursive=False, delete_nullable=False):
        logger.warning('Deleting user: %s', self)
        return super(AuthorizedUser, self).delete_instance(recursive=recursive, delete_nullable=delete_nullable)
    
    
    def get_username(self):
        return '@%s' % self.username if self.username else None
    
    
    def save(self, update_last_connection=True, *args, **kwargs):
        if update_last_connection:
            self.last_connection = datetime.datetime.now()
        return super(AuthorizedUser, self).save(*args, **kwargs)
    
    
    def is_authorized(self):
        return not self.blocked
    
    
    def is_banned(self):
        if self.is_authorized():
            return False
        return self.access_requested_count > settings.REQUESTED_ACCESS_FOR_BAN
    
    
    @classmethod
    def _select_from_telegram_user(cls, tg_user):
        if tg_user.id is None and tg_user.username is None:
            raise Exception('telegram_id and username are None!')
        predicate = (
            (cls.telegram_id == tg_user.id) |
            ((cls.username == tg_user.username) &
             (cls.telegram_id == DEFAULT_TELEGRAM_ID))
        )
        return cls.select().where(predicate).limit(1).first()
    
    
    @classmethod
    def from_telegram_user(cls, tg_user, blocked=None, access_requested_count=None, update_db=True, dont_raise=False):
        user = cls._select_from_telegram_user(tg_user)
        if user is None:
            if dont_raise:
                return None
            raise cls.DoesNotExist()
        
        if user.telegram_id in [None, DEFAULT_TELEGRAM_ID] and tg_user.id is not None:
            user.telegram_id = tg_user.id
        if tg_user.first_name is not None:
            user.first_name = tg_user.first_name
        if tg_user.last_name is not None:
            user.last_name = tg_user.last_name
        if tg_user.username is not None:
            user.username = tg_user.username
        if blocked is not None:
            user.blocked = blocked
        if access_requested_count is not None:
            user.access_requested_count = access_requested_count
        
        if update_db:
            user.save()
        return user
    
    
    @classmethod
    def is_authorized_from_telegram_user(cls, tg_user):
        user = cls._select_from_telegram_user(tg_user)
        return user.is_authorized() if user is not None else False
    
    
    @classmethod
    def is_banned_from_telegram_user(cls, tg_user):
        user = cls._select_from_telegram_user(tg_user)
        return user.is_banned() if user is not None else False
    
    
    @classmethod
    def create_from_telegram_user(cls, tg_user, blocked=None, access_requested_count=None):
        user = cls._select_from_telegram_user(tg_user)
        if user is not None:
            raise UserAlreadyException('<%s> already exists: %s' % (cls.__name__, user))
        data = {
            'telegram_id': tg_user.id,
            'first_name': tg_user.first_name,
        }
        if tg_user.last_name is not None:
            data['last_name'] = tg_user.last_name
        if tg_user.username is not None:
            data['username'] = tg_user.username
        if blocked is not None:
            data['blocked'] = blocked
        if access_requested_count is not None:
            data['access_requested_count'] = access_requested_count
        return cls.create(**data)
