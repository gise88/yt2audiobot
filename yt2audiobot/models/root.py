#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import logging
from playhouse.migrate import *

from yt2audiobot import settings
from .base import BaseModel
from .authorizeduser import AuthorizedUser
from .admin import Admin
from .usersutils import DEFAULT_TELEGRAM_ID


logger = logging.getLogger(settings.BOT_NAME)


# http://stackoverflow.com/questions/951686/is-a-one-column-table-good-design
class Root(BaseModel):
    admin = ForeignKeyField(Admin, primary_key=True)
    
    
    @classmethod
    def get_root_chat_id(cls):
        q = Admin.select(Admin.chat_id).join(cls)
        return [admin.chat_id for admin in q]
    
    
    @classmethod
    def exists_from_telegram_user(cls, tg_user):
        if tg_user.id is None and tg_user.username is None:
            raise Exception('telegram_id and username are None!')
        predicate = (
            (AuthorizedUser.telegram_id == tg_user.id) |
            ((AuthorizedUser.username == tg_user.username) &
             (AuthorizedUser.telegram_id == DEFAULT_TELEGRAM_ID))
        )
        return cls.select().join(Admin).join(AuthorizedUser).where(predicate).exists()
