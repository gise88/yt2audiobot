#!/usr/bin/env python
# -*- coding: utf-8 -*-


DEFAULT_TELEGRAM_ID = 0


class UserAlreadyException(Exception):
    pass


class TelegramUser(object):
    def __init__(self, id, first_name, last_name, username):
        self.id = id
        self.first_name = first_name
        self.last_name = last_name
        self.username = username
