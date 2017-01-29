#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from peewee import Model
from peewee import SqliteDatabase


_database = SqliteDatabase(None)


def get_database():
    return _database


class BaseModel(Model):
    class Meta:
        database = get_database()
    
    
    @classmethod
    def get_field_names(cls):
        return cls._meta.sorted_fields