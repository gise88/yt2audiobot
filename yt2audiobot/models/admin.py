#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import logging
from playhouse.migrate import *

from yt2audiobot import settings
from .base import BaseModel
from .authorizeduser import AuthorizedUser
from .usersutils import DEFAULT_TELEGRAM_ID
from .usersutils import UserAlreadyException


logger = logging.getLogger(settings.BOT_NAME)


class Admin(BaseModel):
    authorized_user = ForeignKeyField(AuthorizedUser, primary_key=True)
    # I don't really know if chat_id is needed but store an integer field is not a big problem, so..
    chat_id = IntegerField(default=DEFAULT_TELEGRAM_ID, unique=True)
    
    
    def __repr__(self):
        return '<Admin: \n' \
               '  authorized_user.telegram_id = {s.authorized_user.telegram_id!r}\n' \
               '  authorized_user.first_name = {s.authorized_user.first_name!r}\n' \
               '  authorized_user.last_name = {s.authorized_user.last_name!r}\n' \
               '  authorized_user.username = {s.authorized_user.username!r}\n' \
               '  authorized_user.blocked = {s.authorized_user.blocked!r}\n' \
               '  authorized_user.access_requested_count = {s.authorized_user.access_requested_count!r}\n' \
               '  chat_id={s.chat_id!r}>'.format(s=self)
    
    
    def __str__(self):
        return '{auth_user} ' \
               'chat_id:{chat_id}'.format(auth_user=self.authorized_user, chat_id=self.chat_id)
    
    
    def delete_instance(self, recursive=False, delete_nullable=False):
        logger.warning('Deleting admin: %s', self)
        return super(Admin, self).delete_instance(recursive=recursive, delete_nullable=delete_nullable)
    
    
    @classmethod
    def _select_from_telegram_user(cls, tg_user):
        if tg_user.id is None and tg_user.username is None:
            raise Exception('telegram_id and username are None!')
        predicate = (
            (AuthorizedUser.telegram_id == tg_user.id) |
            ((AuthorizedUser.username == tg_user.username) &
             (AuthorizedUser.telegram_id == DEFAULT_TELEGRAM_ID))
        )
        return cls.select().join(AuthorizedUser).where(predicate).limit(1).first()
    
    
    @classmethod
    def from_telegram_user(cls, tg_user, chat_id=None, update_db=True, dont_raise=False):
        admin = cls._select_from_telegram_user(tg_user)
        if admin is None:
            if dont_raise:
                return None
            raise cls.DoesNotExist()
        
        user = admin.authorized_user
        
        if user.telegram_id in [None, DEFAULT_TELEGRAM_ID] and tg_user.id is not None:
            user.telegram_id = tg_user.id
        if tg_user.first_name is not None:
            user.first_name = tg_user.first_name
        if tg_user.last_name is not None:
            user.last_name = tg_user.last_name
        if tg_user.username is not None:
            user.username = tg_user.username
        if chat_id is not None:
            admin.chat_id = chat_id
        
        if update_db:
            admin.save()
            user.save()
        return admin
    
    
    @classmethod
    def exists_from_telegram_user(cls, tg_user):
        return cls._select_from_telegram_user(tg_user) is not None
    
    
    @classmethod
    def create_from_telegram_user(cls, tg_user, chat_id=None, *args):
        user = cls._select_from_telegram_user(tg_user)
        if user is not None:
            raise UserAlreadyException('<%s> already exists: %s' % (cls.__name__, user))
        user = AuthorizedUser.from_telegram_user(
            tg_user, blocked=False, access_requested_count=0, update_db=True
        )
        if user is None:
            user = AuthorizedUser.create_from_telegram_user(
                tg_user, blocked=False, access_requested_count=0
            )
        data = {
            'authorized_user': user,
            'chat_id': chat_id if chat_id is not None else DEFAULT_TELEGRAM_ID
        }
        return cls.create(**data)
