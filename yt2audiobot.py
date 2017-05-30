#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals

import json
import logging
import re
import sys
import time
import traceback

import requests
import telebot
from emoji import emojize

from yt2audiobot import settings
from yt2audiobot import dbmanager
from yt2audiobot.models import Admin
from yt2audiobot.models import AudioDBController
from yt2audiobot.models import AuthorizedUser
from yt2audiobot.models import Root
from yt2audiobot.models import TelegramUser
from yt2audiobot.models import UserAlreadyException
from yt2audiobot.ythelper import DownloadError
from yt2audiobot.ythelper import FileIsTooLargeException
from yt2audiobot.ythelper import YTHelper
from yt2audiobot.spotifyhelper import Spotify


logger = logging.getLogger(settings.BOT_NAME)
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

YOUTUBE_REGEX = '^((http(s)?:\/\/)?)(www\.)?(m\.)?((youtube\.com\/)|(youtu.be\/))[\S]+'

MESSAGE_YOU_HAVE_BEEN_BANNED = emojize(
    'You have been banned because of too many access requests! :expressionless_face:')


class ExceptionCatcherTeleBot(telebot.TeleBot, object):
    def __init__(self, token, threaded=True, skip_pending=False):
        self.exception_handler = None
        if threaded:
            # TODO: make ExceptionCatcherTeleBot works with threaded = True
            raise RuntimeError('ExceptionCatcherTeleBot can works only with threaded = false by now. '
                               'Future updates will come!')
        super(ExceptionCatcherTeleBot, self).__init__(token, threaded=threaded, skip_pending=skip_pending)
    
    
    def set_exception_handler(self, exception_handler):
        if callable(exception_handler):
            self.exception_handler = exception_handler
        else:
            raise TypeError('Exception Handler is not a function')
    
    
    def polling(self, none_stop=False, interval=0, timeout=20):
        if self.exception_handler is None:
            raise RuntimeError('Exception Handler has not been specified! Please use: set_exception_handler to set it.')
        super(ExceptionCatcherTeleBot, self).polling(none_stop=none_stop, interval=interval, timeout=timeout)
    
    
    def _exec_task(self, task, *args, **kwargs):
        if self.threaded:
            self.worker_pool.put(task, *args, **kwargs)
        else:
    
            logger.debug(len(args))
            try:
                task(*args, **kwargs)
            except Exception as e:
                # args[0] contains the message
                self.exception_handler(args[0], traceback.format_exc())


class ParseException(Exception):
    pass


class InlineKeyboardButtonCallbackDataOverflow(Exception):
    pass


class InlineKeyboardButtonActCidMid(telebot.types.InlineKeyboardButton, object):
    def __init__(self, text, action, chat_id, message_id):
        callback_data = json.dumps({
            'act': action,
            'cid': chat_id,
            'mid': message_id
        }, separators=(',', ':'))
        
        # https://core.telegram.org/bots/api#inlinekeyboardbutton
        if len(callback_data) > 64:
            raise InlineKeyboardButtonCallbackDataOverflow(callback_data)
        
        super(InlineKeyboardButtonActCidMid, self).__init__(text, callback_data=callback_data)


def start_bot():
    logger.info('start_bot()')
    
    user_commands = {  # command description used in the 'help' command
        # 'start': 'This command will show you your Telegram ID. ' + \
        #          'In order to use this bot, give this information to an admin! ' + \
        #          'As long as you know one of them.. ' + Emoji.SMIRKING_FACE,
        'help': 'Gives you information about the available commands',
        'getMp3': 'Download and convert the video and send back to you the mp3. \n' + \
                  'Example:\n/getMp3 https://www.youtube.com/watch?v=dQw4w9WgXcQ \n'
    }
    
    admin_commands = {  # command description used in the 'help' command
        'addUser': 'Create a new authorized user from telegram id or username.\n' + \
                   'Example:\n/addUser username or\n/addUser 12345678'
    }
    
    root_commands = {  # command description used in the 'help' command
        'addAdmin': 'Create a new authorized admin from telegram id or username.\n' + \
                    'Example:\n/addAdmin username or\n/addAdmin 12345678'
    }

    dbmanager.connect_to_db(
        settings.ABS_PATH_USERS_DB,
        settings.BOT_SECRETS['yt2audiobot_root']
    )
    audio_db = AudioDBController()
    
    bot = ExceptionCatcherTeleBot(settings.BOT_SECRETS['telegram_token'],
                                  threaded=False)  # in the future maybe will be threaded
    bot_me = bot.get_me()
    logger.info(bot_me)
    
    class YTHelperProgressHook(object):
        STATUS_TO_MESSAGE = {
            'getting_information': lambda h: 'Getting video information',
            'information_downloaded': lambda h: 'Information retrieved! Starting download the %s..' % h['type'],
            'already_downloaded': lambda h: 'Audio found in the database. Already downloaded %d %s' %
                                            (h['downloaded_times'], 'time' if h['downloaded_times'] == 1 else 'times'),
            'downloading': lambda h: '[%s] Downloading at %s' % (h['_percent_str'], h['_speed_str']),
            'finished': lambda h: 'Download finished: %s\nStart extracting audio postprocess..' % h['_total_bytes_str'],
            'searching_metadata': lambda h: 'Searching audio metadata from Spotify and Musixmatch',
            'upload_audio': lambda h: 'Uploading...',
            'done': lambda h: emojize('Done! :white_heavy_check_mark:')
        }
        
        
        def __init__(self, bot, chat_id, message_id):
            self._bot = bot
            self._chat_id = chat_id
            self._message_id = message_id
            self._count = 0
        
        
        def get_progress_hook(self):
            return self._progress_hook
        
        
        def notify_progress(self, hook):
            self._progress_hook(hook)
        
        
        def _progress_hook(self, hook, youtube_video=None):
            try:
                text = ''
                if youtube_video:
                    text += '%s\n%s\n\n' % (youtube_video.get_video_title(), youtube_video.get_url())
                
                text += self.STATUS_TO_MESSAGE[hook['status']](hook)
                
                self._bot.edit_message_text(text, self._chat_id, self._message_id, disable_web_page_preview=True)
                # self._bot.send_message(self._chat_id, text, disable_web_page_preview=True)
            except KeyError as e:
                root_chat_ids = Root.get_root_chat_id()
                for chat_id in root_chat_ids:
                    bot.send_message(chat_id, str(e))
    
    def stringify_user(from_user):
        text = '[{0}] {1}'.format(from_user.id, from_user.first_name)
        if from_user.last_name:
            text += ' {0}'.format(from_user.last_name)
        if from_user.username:
            text += ' @{0}'.format(from_user.username)
        return text
    
    
    def log_user_start(user):
        logger.info('user start %s', stringify_user(user))
    
    
    def get_start_text(uid):
        return emojize('Welcome to %s!! :v:\n\nYour Telegram ID is: %d\n\n'
                       'This code can be used by an admin to add your account to the white list. :muscle:\n'
                       'If you don\'t know any Admins, who could do this for you, I\'m sorry but '
                       'I cannot manage to give the access to the entire world.. :sob:' % (
                           bot_me.first_name,
                           uid
                       ), use_aliases=True)
    
    
    def update_admin_user(m):
        if m.chat.type == 'private':
            Admin.from_telegram_user(m.from_user, chat_id=m.chat.id, dont_raise=True)
    
    
    def username_or_telegram_id(text):
        if len(text) > 3:
            try:
                telegram_id = [int(s) for s in text.split() if s.isdigit()][0]
                return TelegramUser(telegram_id, None, None, None)
            except IndexError:
                m = re.search('^(#?@?)([a-zA-Z0-9_]+)', text)
                if m is not None:
                    without_at = m.group(2)
                    # https://core.telegram.org/method/account.checkUsername
                    if len(without_at) < 5 or len(without_at) > 32:
                        raise ParseException('username length: 5-32 characters')
                    return TelegramUser(None, None, None, without_at)
        raise ParseException(
            'ID Accepted characters: A-z (case-insensitive), 0-9 and underscores.Length: 5-32 characters.')
    
    
    def handle_youtube_link(m):
        cid = m.chat.id
        r = re.search(YOUTUBE_REGEX, m.text)
        if r is not None:
            youtube_url = r.group(0)
            reply_message = bot.reply_to(m, 'Managing your request...')
            yth_progress_hook = YTHelperProgressHook(bot, cid, reply_message.message_id)
            yt_helper = YTHelper(youtube_url, yth_progress_hook.get_progress_hook())
            
            for ytvideo in yt_helper.manage_url():
                youtube_id = ytvideo.get_youtube_id()
                yt2tg_mapping, _ = audio_db.search_by_youtube_or_telegram_file(youtube_id=youtube_id)
                
                if yt2tg_mapping:
                    yth_progress_hook.notify_progress({
                        'status': 'already_downloaded',
                        'downloaded_times': yt2tg_mapping.downloaded_times
                    })
                    bot.send_audio(cid, yt2tg_mapping.telegram_file_id, caption='Downloaded using @yt2audiobot')
                    yt2tg_mapping.downloaded_times += 1
                    yt2tg_mapping.save()
                else:
                    try:
                        data = ytvideo.download_video_and_extract_audio()
                        audio = open(data['filename'], 'rb')
                        yth_progress_hook.notify_progress({
                            'status': 'upload_audio'
                        })
                        bot.send_chat_action(cid, 'upload_audio')
                        audio_message = bot.send_audio(cid, audio, caption='Downloaded using @yt2audiobot').audio
                        data['youtube_id'] = youtube_id
                        data['telegram_file_id'] = audio_message.file_id
                        data['file_size'] = audio_message.file_size
                        data['duration'] = audio_message.duration
                        audio_db.add_youtube_telegram_file_entry_and_metadata(**data)
                    except DownloadError as e:
                        logger.error('[Download Error] %s', e)
                        bot.send_message(cid, str(e))
                    except FileIsTooLargeException as e:
                        logger.error('[File Is Too Large] %s', e)
                        bot.send_message(cid, str(e), disable_web_page_preview=True)
            
            yth_progress_hook.notify_progress({
                'status': 'done'
            })
        
        else:
            bot.send_message(cid, 'Sorry, it is not a valid youtube link!')
    
    
    def manage_exception(message, str_exception):
        root_chat_ids = Root.get_root_chat_id()
        logger.debug(message)
        if hasattr(message, 'chat') and message.chat.id not in root_chat_ids:
            bot.reply_to(message, emojize('Oooops! Something went wrong! :face_with_cold_sweat:'))
        for chat_id in root_chat_ids:
            if hasattr(message, 'chat') and message.chat.id not in root_chat_ids:
                bot.forward_message(chat_id, message.chat.id, message.message_id)
            bot.send_message(chat_id, str(str_exception))
            logger.error(str_exception)
        
        
    def remove_admin(root_cid, admin_user, auth_user):
        msg = bot.send_message(root_cid, emojize(
            'Going to downgrade the Admin: {0} :smirking_face:\n'.format(admin_user)))
        deleted_rows = admin_user.delete_instance()
        bot.edit_message_text(emojize(
            'Done! Downgraded successfully for user: {0} :thumbs_up_sign: \n'
            '(deleted rows: {1})'.format(auth_user, deleted_rows)), root_cid, msg.message_id)
    
    
    def add_user_from_type(m, class_type):
        cid = m.chat.id
        try:
            text = m.text.split(' ', 1)[1]
            try:
                tg_user = username_or_telegram_id(text)
                try:
                    class_type.create_from_telegram_user(tg_user, blocked=False, access_requested_count=0)
                    bot.send_message(cid, emojize('Done! :thumb_up_sign:'))
                except UserAlreadyException as e:
                    bot.send_message(cid, emojize('{0}.. :neutral_face:'.format(e)))
            except ParseException as e:
                bot.send_message(cid, str(e))
        except IndexError as e:
            pass
    
    
    #### TELEGRAM BOT HANDLERS ####
    
    
    @bot.message_handler(commands=['help'])
    def handle_help(m):
        cid = m.chat.id
        update_admin_user(m)
        if AuthorizedUser.is_authorized_from_telegram_user(m.from_user):
            help_text = 'The following commands are available: \n'
            for key in user_commands:
                help_text += '/%s: %s\n' % (key, user_commands[key])
            if Admin.exists_from_telegram_user(m.from_user):
                for key in admin_commands:
                    help_text += '/%s: %s\n' % (key, admin_commands[key])
                if Root.exists_from_telegram_user(m.from_user):
                    for key in root_commands:
                        help_text += '/%s: %s\n' % (key, root_commands[key])
            
            bot.send_message(cid, help_text, disable_web_page_preview=True)
    
    
    @bot.message_handler(commands=['start'])
    def handle_start(m):
        if not m.chat.type == 'private':
            bot.reply_to(m, '/start command can only be used in the private chats')
            return
        
        cid = m.chat.id
        uid = m.from_user.id
        log_user_start(m.from_user)
        # TODO: if the user already has the access just print the help message
        update_admin_user(m)
        
        markup = telebot.types.InlineKeyboardMarkup()
        btn_visit_github = telebot.types.InlineKeyboardButton('Github', url=settings.URL_REPO_GITHUB)
        
        try:
            user = AuthorizedUser.from_telegram_user(m.from_user)
            logger.debug(user)
            if user.is_banned():
                start_text = MESSAGE_YOU_HAVE_BEEN_BANNED
                sent_message = bot.send_message(cid, start_text)
                markup.row(btn_visit_github)
            elif user.is_authorized():
                return handle_help(m)
        except AuthorizedUser.DoesNotExist:
            start_text = get_start_text(uid)
            sent_message = bot.send_message(cid, start_text)
            btn_ask_access = InlineKeyboardButtonActCidMid('Ask for access', 'req_access', cid,
                                                           sent_message.message_id)
            markup.row(btn_ask_access, btn_visit_github)
        
        bot.edit_message_reply_markup(chat_id=cid, message_id=sent_message.message_id, reply_markup=markup)
    
    
    @bot.callback_query_handler(func=lambda call: json.loads(call.data)['act'] == 'req_access')
    def btn_req_access(call):
        uid = call.from_user.id
        callback_data = json.loads(call.data)
        cid = callback_data['cid']
        mid = callback_data['mid']
        
        if AuthorizedUser.is_banned_from_telegram_user(call.from_user):
            start_text = MESSAGE_YOU_HAVE_BEEN_BANNED
            markup = telebot.types.InlineKeyboardMarkup()
            markup.add(telebot.types.InlineKeyboardButton('Github', url=settings.URL_REPO_GITHUB))
            bot.edit_message_text(start_text, cid, mid, reply_markup=markup)
        else:
            callback_data = json.loads(call.data)
            cid = callback_data['cid']
            mid = callback_data['mid']
            
            markup_buttons_rows = [
                [
                    InlineKeyboardButtonActCidMid('Agree as user', 'agree_user', cid, mid),
                    InlineKeyboardButtonActCidMid('Agree as admin', 'agree_admin', cid, mid)
                ],
                [
                    InlineKeyboardButtonActCidMid('Deny', 'deny_user', cid, mid),
                    InlineKeyboardButtonActCidMid('Ban!', 'ban_user', cid, mid)
                ]
            ]
            
            markup_buttons_root = telebot.types.InlineKeyboardMarkup()
            for row in markup_buttons_rows:
                markup_buttons_root.add(*row)
            
            root_chat_ids = Root.get_root_chat_id()
            for chat_id in root_chat_ids:
                req_text = 'The user:\n%s\nrequests the access to use %s!' % \
                           (stringify_user(call.from_user), bot_me.username)
                bot.send_message(chat_id, req_text, reply_markup=markup_buttons_root)
            
            start_text = get_start_text(uid)
            start_text += emojize('\n\nAccess requested :watch:')
            markup = telebot.types.InlineKeyboardMarkup()
            markup.add(telebot.types.InlineKeyboardButton('Github', url=settings.URL_REPO_GITHUB))
            bot.edit_message_text(start_text, cid, mid, reply_markup=markup)
            bot.answer_callback_query(call.id, text='Access requested')
        
        # registry user
        try:
            auth_user = AuthorizedUser.from_telegram_user(call.from_user)
            if auth_user.blocked:
                auth_user.access_requested_count += 1
                auth_user.save()
        except AuthorizedUser.DoesNotExist:
            AuthorizedUser.create_from_telegram_user(
                call.from_user,
                blocked=True,
                access_requested_count=1
            )
    
    
    @bot.callback_query_handler(func=lambda call: json.loads(call.data)['act'] == 'agree_user')
    @bot.callback_query_handler(func=lambda call: json.loads(call.data)['act'] == 'agree_admin')
    @bot.callback_query_handler(func=lambda call: json.loads(call.data)['act'] == 'deny_user')
    @bot.callback_query_handler(func=lambda call: json.loads(call.data)['act'] == 'ban_user')
    def btn_give_access(call):
        callback_data = json.loads(call.data)
        user_cid = callback_data['cid']
        user_mid = callback_data['mid']
        root_cid = call.message.chat.id
        start_text = get_start_text(user_cid)
        tg_user = TelegramUser(user_cid, None, None, None)
        
        # check if the user who press the button is root and make sure that the target is not the root
        if Root.exists_from_telegram_user(call.from_user) and not Root.exists_from_telegram_user(tg_user):
            
            try:
                # if the user doesn't exist it will raise an exception.
                auth_user = AuthorizedUser.from_telegram_user(tg_user)
                admin_user = Admin.from_telegram_user(tg_user, dont_raise=True)
                
                if callback_data['act'] in ['agree_user', 'agree_admin']:
                    
                    if callback_data['act'] == 'agree_user':
                        start_text += emojize('\n\nAccess agreed!! :white_heavy_check_mark:')
                        if admin_user is None:
                            bot.send_message(root_cid, emojize('Done! :thumbs_up_sign: \n'
                                                               '(already was an auth user: {0})'.format(not auth_user.blocked)))
                        
                        # if he/she was an admin and not the root needs to be removed
                        else:
                            remove_admin(root_cid, admin_user, auth_user)
                    
                    elif callback_data['act'] == 'agree_admin':
                        start_text += emojize('\n\nAccess agreed as admin!! :party_popper:')
                        try:
                            # Since I get the cid from a private chat uid = cid
                            Admin.create_from_telegram_user(tg_user, chat_id=user_cid)
                            bot.send_message(root_cid, emojize('Done! :thumbs_up_sign:'))
                        except UserAlreadyException as e:
                            bot.send_message(root_cid, emojize('{0}.. :neutral_face:'.format(e)))
                    
                    auth_user.blocked = False
                    auth_user.access_requested_count = 0
                    auth_user.save()
                
                elif callback_data['act'] in ['deny_user', 'ban_user']:
                    if admin_user is not None:
                        remove_admin(root_cid, admin_user, auth_user)
                    
                    auth_user.blocked = True
                    if callback_data['act'] == 'ban_user':
                        auth_user.access_requested_count = settings.REQUESTED_ACCESS_FOR_BAN + 1
                        start_text = MESSAGE_YOU_HAVE_BEEN_BANNED
                    
                    bot.send_message(root_cid, emojize('Done! :thumbs_up_sign:'))
                    auth_user.save()
                else:
                    raise Exception('Action unknown: {0}'.format(callback_data['act']))
                
                try:
                    markup = telebot.types.InlineKeyboardMarkup()
                    markup.add(telebot.types.InlineKeyboardButton('Github', url=settings.URL_REPO_GITHUB))
                    bot.edit_message_text(start_text, user_cid, user_mid, reply_markup=markup)
                except telebot.apihelper.ApiException as e:
                    if 'message is not modified' not in json.loads(e.result.text)['description']:
                        raise e
            except AuthorizedUser.DoesNotExist as e:
                bot.send_message(root_cid, emojize('{0}.. :neutral_face:'.format(e)))
        
        elif not Root.exists_from_telegram_user(call.from_user):
            bot.send_message(call.message.chat.id, 'This command can only be used by admin users')
            root_chat_ids = Root.get_root_chat_id()
            for chat_id in root_chat_ids:
                warning_text = '[WARNING] The user:\n%s\ntries to send a callback query!\n\n' \
                               'call.data:\n%s' % (stringify_user(call.from_user), call.data)
                bot.send_message(chat_id, warning_text)
    
    
    @bot.message_handler(commands=['addUser', 'adduser'])
    def handle_add_user(m):
        if Admin.exists_from_telegram_user(m.from_user):
            add_user_from_type(m, AuthorizedUser)
        else:
            bot.send_message(m.chat.id, 'This command can be used only by admin users')
    
    
    @bot.message_handler(commands=['addAdmin', 'addadmin'])
    def handle_add_admin(m):
        cid = m.chat.id
        if Root.exists_from_telegram_user(m.from_user):
            update_admin_user(m)
            add_user_from_type(m, Admin)
        else:
            bot.send_message(cid, 'This command can be used only by root user')
    
    
    @bot.message_handler(regexp=YOUTUBE_REGEX, func=lambda m: m.chat.type == 'private')
    def handle_youtube_link_regex(m):
        if AuthorizedUser.is_authorized_from_telegram_user(m.from_user):
            update_admin_user(m)
            handle_youtube_link(m)
    
    
    get_mp3_commands_array = ['getMp3', 'getmp3', 'mp3']
    
    
    @bot.message_handler(commands=get_mp3_commands_array)
    def handle_youtube_link_commands(m):
        if AuthorizedUser.is_authorized_from_telegram_user(m.from_user):
            update_admin_user(m)
            if '@' + bot_me.username in m.text:
                m.text = m.text.replace('@' + bot_me.username, '')
            if len(m.text.split(' ')) == 2:
                m.text = m.text.split(' ', 1)[1]
            else:
                for command in get_mp3_commands_array:
                    m.text = m.text.replace(command, '')
            
            handle_youtube_link(m)
    
    
    while True:
        try:
            logger.info('bot.polling')
            bot.set_exception_handler(manage_exception)
            bot.polling(none_stop=True, interval=3)
        except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout) as e:
            logger.error(e)
            time.sleep(15)  # used to avoid temporary errors
        except Exception:
            logger.error(traceback.format_exc())
            for chat_id in Root.get_root_chat_id():
                bot.send_message(chat_id, str(traceback.format_exc()))
            exit(1)


if __name__ == '__main__':
    create_db_args = ['db', 'createdb', 'startdb', 'database']
    try:
        with open(settings.SECRETS_PATH, 'r') as f:
            settings.BOT_SECRETS['yt2audiobot_root'] = f.readline().strip()
            settings.BOT_SECRETS['telegram_token'] = f.readline().strip()
            settings.BOT_SECRETS['musixmatch_key'] = f.readline().strip()
            settings.BOT_SECRETS['spotify_client_id'] = f.readline().strip()
            settings.BOT_SECRETS['spotify_client_secret'] = f.readline().strip()

            Spotify.authenticate()
            
            if len(sys.argv) == 1:
                start_bot()
            elif len(sys.argv) == 2 and sys.argv[1] in create_db_args:
                dbmanager.initialize_db(
                    settings.ABS_PATH_USERS_DB,
                    settings.BOT_SECRETS['yt2audiobot_root']
                )
            else:
                logger.error('Invalid argument(s): %s!\n'
                             'Please simply run the bot without any argument or '
                             'initialize the db with \'createdb\'' % sys.argv[1:], file=sys.stderr)
    
    except IOError as e:
        logger.error(e)
