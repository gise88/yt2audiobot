#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import re
import os
import logging
import unicodedata
from yt2audiobot import settings

logger = logging.getLogger(settings.BOT_NAME)


class TermColors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def strip_accents(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s)
                   if unicodedata.category(c) != 'Mn')


# thanks to django: https://github.com/django/django/blob/master/django/utils/text.py
def get_valid_filename(s):
    """
    Returns the given string converted to a string that can be used for a clean
    filename. Specifically, leading and trailing spaces are removed; other
    spaces are converted to underscores; and anything that is not a unicode
    alphanumeric, dash, underscore, or dot, is removed.
    >>> get_valid_filename("john's portrait in 2004.jpg")
    'Johns Portrait In 2004.jpg'
    """

    s = s.replace('Ø', 'o')
    s = strip_accents(s)
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore')
    s = re.sub('[^\w\s-]', '', s).strip().lower().title()[:80]
    
    return s


def rename_file(old_filename, new_filename):
    full_path, filename = os.path.split(old_filename)
    filename, extension = os.path.splitext(filename)
    temp_filename = os.path.join(full_path, new_filename + extension)
    os.rename(old_filename, temp_filename)
    return temp_filename


def format_size(size):
    units = ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB']
    size = float(size)
    i = 0
    while size >= 1024.0 and i < len(units):
        i += 1
        size /= 1024.0
    return "%.2f %s" % (size, units[i])
