#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals, absolute_import

import peewee
import logging
import datetime
from six.moves import input
from playhouse.migrate import *

from yt2audiobot.utils import TermColors
from yt2audiobot import settings


logger = logging.getLogger(settings.BOT_NAME)

DEFAULT_TELEGRAM_ID = 0
_users_db = SqliteDatabase(None)


class UserAlreadyException(Exception):
    pass


class TelegramUser(object):
    def __init__(self, id, first_name, last_name, username):
        self.id = id
        self.first_name = first_name
        self.last_name = last_name
        self.username = username


class BaseModel(Model):
    class Meta:
        database = _users_db
    
    def __str__(self):
        return self.__repr__()
    
    
    @classmethod
    def get_field_names(cls):
        return cls._meta.sorted_fields


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
    
    
    def get_username(self):
        return '@%s' % self.username if self.username else None
    
    
    def save(self, *args, **kwargs):
        self.last_connection = datetime.datetime.now()
        return super(AuthorizedUser, self).save(*args, **kwargs)
    
    
    def is_authorized(self):
        return not self.blocked
    
    
    def is_banned(self):
        if self.is_authorized():
            return False
        return self.access_requested_count > settings.REQUESTED_ACCESS_FOR_BAN
    
    
    # def is_admin(self):
    #     predicate = (
    #         (AuthorizedUser.telegram_id == self.id) |
    #         ((AuthorizedUser.username == self.username) &
    #          (AuthorizedUser.telegram_id == DEFAULT_TELEGRAM_ID))
    #     )
    #     return Admin.select().join(AuthorizedUser).where(predicate).exists()
    #
    #
    # def is_root(self):
    #     predicate = (
    #         (AuthorizedUser.telegram_id == self.id) |
    #         ((AuthorizedUser.username == self.username) &
    #          (AuthorizedUser.telegram_id == DEFAULT_TELEGRAM_ID))
    #     )
    #     return Admin.select().join(AuthorizedUser).where(predicate).exists()
    
    
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
            'last_name': tg_user.last_name,
            'username': tg_user.username
        }
        if blocked is not None:
            data['blocked'] = blocked
        if access_requested_count is not None:
            data['access_requested_count'] = access_requested_count
        return cls.create(**data)


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
    def create_from_telegram_user(cls, tg_user, chat_id=None):
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


class UsersDBController(object):
    USER_DB_MODELS = [AuthorizedUser, Admin, Root]
    
    class RootDoesNotExistException(Exception):
        pass
    
    class RootIsConfiguredIncorrectlyException(Exception):
        pass
    
    @classmethod
    def _init_and_connect(cls, db, path):
        db.init(path)
        db.connect()
    
    
    @classmethod
    def _create_tables(cls, db):
        db.create_tables(cls.USER_DB_MODELS, safe=True)
    
    
    @classmethod
    def _drop_tables(cls, db):
        db.drop_tables(cls.USER_DB_MODELS, safe=True)
    
    
    @classmethod
    def _check_root(cls, predicate):
        root_count = AuthorizedUser.select().where(predicate).count()
        root_count += Admin.select().join(AuthorizedUser).where(predicate).count()
        root_count += Root.select().join(Admin).join(AuthorizedUser).where(predicate).count()
        
        if root_count == 0:
            raise cls.RootDoesNotExistException('root_count = %d' % root_count)
        elif root_count != len(cls.USER_DB_MODELS):
            raise cls.RootIsConfiguredIncorrectlyException('root_count = %d' % root_count)
    
    
    @classmethod
    def _initialize_root(cls, predicate, root_username):
        try:
            Root.select().join(Admin).join(AuthorizedUser).where(predicate).get()
            logger.info('Root %s is already initialized', root_username)
        except Root.DoesNotExist:
            # reset of all database
            root_user = AuthorizedUser.create(first_name='Root', last_name='Root', username=root_username)
            root_admin = Admin.create(authorized_user=root_user)
            Root.create(admin=root_admin)
            cls._check_root(predicate)
            logger.info('Root %s initialization completed!', root_username)
    
    
    @classmethod
    def connect_to_db(cls, path, root_username):
        cls._init_and_connect(_users_db, path)
        cls._check_root(AuthorizedUser.username == root_username)
        logger.info('Welcome %s', root_username)
    
    
    @classmethod
    def initialize_db(cls, path, root_username):
        db = _users_db
        cls._init_and_connect(db, path)
        predicate = AuthorizedUser.username == root_username
        
        try:
            cls._check_root(predicate)
        except peewee.OperationalError as e:
            for table in cls.USER_DB_MODELS:
                if table.table_exists():
                    # some tables exist but some others don't
                    raise Exception('ERROR: %s - but %s exists' % (e, table.__name__))
            cls._drop_tables(db)
            cls._create_tables(db)
        except (cls.RootDoesNotExistException, cls.RootIsConfiguredIncorrectlyException) as e:
            user_answer = input(
                '%sWarning:  %s\nSomething went wrong in the database and seems to '
                'be missing the root user (or something else)!\nNeed to drop all tables and '
                'recreate them all.\n\nDo you want to continue? [Type \'yes\' to proceed] %s' % (
                    TermColors.WARNING,
                    str(e),
                    TermColors.ENDC
                ))
            if user_answer == 'yes':
                cls._drop_tables(db)
                cls._create_tables(db)
            else:
                exit(1)
        
        cls._initialize_root(predicate, root_username)
        cls.verify_migrations(db)
    
    
    @classmethod
    def verify_migrations(cls, db):
        logger.warning('Watching for migrations..')
        migrator = SqliteMigrator(db)
        apply_migrations = False
        already_asked = False
        
        for table in cls.USER_DB_MODELS:
            table_fields = table.get_field_names()
            column_names = [c.name for c in db.get_columns(table.__name__)]
            
            for field in table_fields:
                if field.name not in column_names and field.name + '_id' not in column_names:
                    if not apply_migrations:
                        
                        if not already_asked:
                            user_answer = input(
                                '%sWarning: Some database schema is changed.'
                                '\n\nDo you want to continue? [Type \'yes\' to proceed] %s' % (
                                    TermColors.WARNING,
                                    TermColors.ENDC
                                ))
                            already_asked = True
                            if user_answer == 'yes':
                                apply_migrations = True
                        
                        logger.warning('\n%sCreate new column: \'%s\' <type: %s> in %s? -> %s%s\n' %
                                       (TermColors.OKGREEN if apply_migrations else TermColors.FAIL,
                                        field.name,
                                        type(field),
                                        table.__name__,
                                        apply_migrations,
                                        TermColors.ENDC))
                        if apply_migrations:
                            cls._alter_database(db, migrator, table.__name__, field.name, field)
    
    
    @classmethod
    def _alter_database(cls, db, migrator, table_name, column_name, column_field):
        if column_name in db.get_columns(table_name):
            return
        
        with db.transaction():
            migrate(migrator.add_column(table_name, column_name, column_field))

