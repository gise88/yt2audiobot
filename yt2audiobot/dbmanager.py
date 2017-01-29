#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import peewee
import logging
from six.moves import input
from playhouse.migrate import migrate
from playhouse.migrate import SqliteMigrator

from yt2audiobot.utils import TermColors
from yt2audiobot import settings

from yt2audiobot.models import get_database
from yt2audiobot.models import AuthorizedUser
from yt2audiobot.models import Admin
from yt2audiobot.models import Root


logger = logging.getLogger(settings.BOT_NAME)


USER_DB_MODELS = [AuthorizedUser, Admin, Root]


class RootDoesNotExistException(Exception):
    pass


class RootIsConfiguredIncorrectlyException(Exception):
    pass


def _init_and_connect(db, path):
    db.init(path)
    db.connect()


def _create_tables(db):
    db.create_tables(USER_DB_MODELS, safe=True)


def _drop_tables(db):
    db.drop_tables(USER_DB_MODELS, safe=True)


def _check_root(predicate):
    root_count = AuthorizedUser.select().where(predicate).count()
    root_count += Admin.select().join(AuthorizedUser).where(predicate).count()
    root_count += Root.select().join(Admin).join(AuthorizedUser).where(predicate).count()
    
    if root_count == 0:
        raise RootDoesNotExistException('root_count = %d' % root_count)
    elif root_count != len(USER_DB_MODELS):
        raise RootIsConfiguredIncorrectlyException('root_count = %d' % root_count)


def _initialize_root(predicate, root_username):
    try:
        Root.select().join(Admin).join(AuthorizedUser).where(predicate).get()
        logger.info('Root %s is already initialized', root_username)
    except Root.DoesNotExist:
        # reset of all database
        root_user = AuthorizedUser.create(first_name='Root', last_name='Root', username=root_username)
        root_admin = Admin.create(authorized_user=root_user)
        Root.create(admin=root_admin)
        _check_root(predicate)
        logger.info('Root %s initialization completed!', root_username)


def _verify_migrations(db):
    logger.warning('Watching for migrations..')
    migrator = SqliteMigrator(db)
    apply_migrations = False
    already_asked = False
    
    for table in USER_DB_MODELS:
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
                        _alter_database(db, migrator, table.__name__, field.name, field)


def _alter_database(db, migrator, table_name, column_name, column_field):
    if column_name in db.get_columns(table_name):
        return
    
    with db.transaction():
        migrate(migrator.add_column(table_name, column_name, column_field))


def connect_to_db(path, root_username):
    _init_and_connect(get_database(), path)
    _check_root(AuthorizedUser.username == root_username)
    logger.info('Welcome %s', root_username)


def initialize_db(path, root_username):
    db = get_database()
    _init_and_connect(db, path)
    predicate = AuthorizedUser.username == root_username
    
    try:
        _check_root(predicate)
    except peewee.OperationalError as e:
        for table in USER_DB_MODELS:
            if table.table_exists():
                # some tables exist but some others don't
                raise Exception('ERROR: %s - but %s exists' % (e, table.__name__))
        _drop_tables(db)
        _create_tables(db)
    except (RootDoesNotExistException, RootIsConfiguredIncorrectlyException) as e:
        user_answer = input(
            '%sWarning:  %s\nSomething went wrong in the database and seems to '
            'be missing the root user (or something else)!\nNeed to drop all tables and '
            'recreate them all.\n\nDo you want to continue? [Type \'yes\' to proceed] %s' % (
                TermColors.WARNING,
                str(e),
                TermColors.ENDC
            ))
        if user_answer == 'yes':
            _drop_tables(db)
            _create_tables(db)
        else:
            exit(1)
    
    _initialize_root(predicate, root_username)
    _verify_migrations(db)