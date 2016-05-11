#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import sys
import time
import telebot
import requests
import settings
import traceback
from emoji import Emoji

from ythelper import YTHelper, PlaylistArgumentError, LimitDurationArgumentError, DownloadError
from usersdbmanager import UsersDBController, UserAlreadyException, UserBlockedException
from audiodbmanager import AudioDBController

#import logging
#logger = telebot.logger
#telebot.logger.setLevel(logging.DEBUG)

def start_bot():
	print "start_bot()"

	user_commands = {  # command description used in the "help" command
		'start': 'This command will show you your Telegram ID. ' + \
				'In order to use this bot, give this information to an admin! ' + \
				'As long as you know one of them.. ' + Emoji.SMIRKING_FACE,
		'help': 'Gives you information about the available commands',
		'getMp3': 'Download and convert the video and send back to you the mp3. \n' + \
				'Example:\n/getMp3 https://www.youtube.com/watch?v=dQw4w9WgXcQ \n'
	}

	admin_commands = {  # command description used in the "help" command
		'addUser': 'Create a new authorized user from telegram id or username.\n' + \
				'Example:\n/addUser username or\n/addUser 12345678'
	}

	root_commands = {  # command description used in the "help" command
		'addAdmin': 'Create a new authorized admin from telegram id or username.\n' + \
				'Example:\n/addAdmin username or\n/addAdmin 12345678'
	}

	users_db = UsersDBController()
	audio_db = AudioDBController()

	bot = telebot.TeleBot(settings.BOT_SECRETS["telegram_token"], threaded=False) # in the future maybe will be threaded
	bot_me = bot.get_me()
	print bot_me

	class ParseException(Exception):
		def __init__(self, message):
			super(ParseException, self).__init__(message)

	def is_user_authorized(m):
		return users_db.is_authorized(telegram_id=m.from_user.id, username=m.from_user.username)

	def update_user(m):
		uid = m.from_user.id
		auth_user = users_db.search_authorized_user(telegram_id=uid, username=m.from_user.username)
		if auth_user is not None:
			auth_user.telegram_id = uid
			auth_user.first_name = m.from_user.first_name
			if m.from_user.last_name is not None:
				auth_user.last_name = m.from_user.last_name
			if m.from_user.username is not None:
				auth_user.username = m.from_user.username
			auth_user.save()
			if m.chat.type == "private":
				admin_user = users_db.search_admin(telegram_id=uid, username=m.from_user.username)
				if admin_user is not None:
					admin_user.chat_id = m.chat.id
					admin_user.save()

	def username_or_telegram_id(text):
		if len(text) > 3:
			try:
				telegram_id = [int(s) for s in text.split() if s.isdigit()][0]
				return { "telegram_id": telegram_id }
			except IndexError:
				m = re.search("^(#?@?)([a-zA-Z0-9_]+)", text)
				if m is not None:
					without_at = m.group(2)
					# https://core.telegram.org/method/account.checkUsername
					if len(without_at) < 5 or len(without_at) > 32: 
						raise ParseException("username length: 5-32 characters")
					return {"username": without_at}
		raise ParseException("ID Accepted characters: A-z (case-insensitive), 0-9 and underscores.Length: 5-32 characters.")

	YOUTUBE_REGEX = "^((http(s)?:\/\/)?)(www\.)?(m\.)?((youtube\.com\/)|(youtu.be\/))[\S]+"
	def handle_youtube_link(m):
		cid = m.chat.id
		m = re.search(YOUTUBE_REGEX, m.text)
		if m is not None:
			youtube_url = m.group(0)
			try:
				ythelper = YTHelper()
				safe_url, youtube_id = ythelper.clean_link(youtube_url)				
				yt2tgmapping, audiometadata = audio_db.search_by_youtube_or_telegram_file(youtube_id=youtube_id)
				if yt2tgmapping is not None:
					bot.send_audio(cid, yt2tgmapping.telegram_file_id)
					yt2tgmapping.downloaded_times += 1
					yt2tgmapping.save()
				else:
					data = ythelper.process_link(safe_url)
					audio = open(data["filename"], 'rb')
					bot.send_chat_action(cid, 'upload_audio')
					audio_message = bot.send_audio(cid, audio).audio
					data["youtube_id"] = youtube_id
					data["telegram_file_id"] = audio_message.file_id
					data["file_size"] = audio_message.file_size
					data["duration"] = audio_message.duration
					audio_db.add_youtube_telegram_file_entry_and_metadata(**data)
			except PlaylistArgumentError as e:
				bot.send_message(cid, "I'm sorry! " + str(e))
			except LimitDurationArgumentError as e:
				bot.send_message(cid, "I'm sorry! " + str(e))
			except DownloadError as e:
				print "[DownloadError]", e
				bot.send_message(cid, str(e))
		else:
			bot.send_message(cid, "Sorry, it is not a valid youtube link!")

	def manage_exception(message, str_exception):
		root_chat_ids = users_db.get_root_chat_id()
		if message.chat.id not in root_chat_ids:
			bot.reply_to(message, 'Oooops! Something went wrong! ' + Emoji.FACE_WITH_COLD_SWEAT)
		for chat_id in root_chat_ids:
			if message.chat.id not in root_chat_ids:
				bot.forward_message(chat_id, message.chat.id, message.message_id)
			bot.send_message(chat_id, str(str_exception))
			print str(str_exception)


	#### TELEGRAM BOT HANDLERS ####


	@bot.message_handler(commands=['help'])
	def handle_help(m):
		try:
			cid = m.chat.id
			if is_user_authorized(m):
				update_user(m)
				help_text = "The following commands are available: \n"
				for key in user_commands:
					help_text += "/" + key + ": "
					help_text += user_commands[key] + "\n"

				if users_db.is_admin(telegram_id=m.from_user.id, username=m.from_user.username):
					for key in admin_commands:
						help_text += "/" + key + ": "
						help_text += admin_commands[key] + "\n"
						
					if users_db.is_root(telegram_id=m.from_user.id, username=m.from_user.username):
						for key in root_commands:
							help_text += "/" + key + ": "
							help_text += root_commands[key] + "\n"

				bot.send_message(cid, help_text)
		except Exception:
			manage_exception(m, traceback.format_exc())

	@bot.message_handler(commands=['start'])
	def handle_start(m):
		try:
			cid = m.chat.id
			uid = m.from_user.id
			user = m.from_user
			print "user start["+str(uid)+"] " + str(user.first_name) +" "+ str(user.last_name) +" "+ str(user.username)

			start_text = "Welcome to " + bot_me.first_name + "!! " + Emoji.VICTORY_HAND + "\n\n" + \
				"Your Telegram ID is: " + str(uid) + "\n\n" + \
				"This code can be used by an admin to add your account to the white list. " + Emoji.FLEXED_BICEPS + "\n" + \
				"If you don't know any Admins, who could do this for you, I'm sorry but " + \
				"I cannot manage to give the access to the entire world.. " + Emoji.CRYING_FACE
			update_user(m)
			bot.send_message(cid, start_text)
		except Exception:
			manage_exception(m, traceback.format_exc())

	@bot.message_handler(commands=['addUser', 'adduser'])
	def handle_add_user(m):
		try:
			cid = m.chat.id
			if users_db.is_admin(telegram_id=m.from_user.id, username=m.from_user.username):
				update_user(m)
				try:
					text = m.text.split(' ', 1)[1]
					try:
						dict = username_or_telegram_id(text)
						try:
							users_db.add_authorized_user(**dict)
							bot.send_message(cid, "Done! " + Emoji.THUMBS_UP_SIGN)
						except UserAlreadyException as e:
							bot.send_message(cid, str(e) + ".. " + Emoji.NEUTRAL_FACE)
					except ParseException as e:
						bot.send_message(cid, str(e))
				except IndexError as e:
					pass
			else:
				bot.send_message(cid, "This command can be used only by admin users")
		except Exception as e:
			manage_exception(m, traceback.format_exc())

	@bot.message_handler(commands=['addAdmin', 'addadmin'])
	def handle_add_admin(m):
		try:
			cid = m.chat.id
			if users_db.is_root(telegram_id=m.from_user.id, username=m.from_user.username):
				update_user(m)
				try:
					text = m.text.split(' ', 1)[1]
					try:
						dict = username_or_telegram_id(text)
						try:
							users_db.add_admin(**dict)
							bot.send_message(cid, "Done! " + Emoji.THUMBS_UP_SIGN)
						except UserAlreadyException as e:
							bot.send_message(cid, str(e) + ".. " + Emoji.NEUTRAL_FACE)
						except UserBlockedException as e:
							bot.send_message(cid, str(e) + ".. " + Emoji.POUTING_FACE)
					except ParseException as e:
						bot.send_message(cid, str(e))
				except IndexError as e:
					pass
			else:
				bot.send_message(cid, "This command can be used only by root user")
		except Exception as e:
			manage_exception(m, traceback.format_exc())

	@bot.message_handler(regexp=YOUTUBE_REGEX)
	def handle_youtube_link_regex(m):
		try:
			if is_user_authorized(m):
				update_user(m)
				handle_youtube_link(m)
		except Exception:
			manage_exception(m, traceback.format_exc())

	get_mp3_commands_array = ['getMp3', 'getmp3', 'mp3']
	@bot.message_handler(commands=get_mp3_commands_array)
	def handle_youtube_link_commands(m):
		try:
			print m.from_user
			if is_user_authorized(m):
				update_user(m)
				if "@" + bot_me.username in m.text:
					m.text = m.text.replace("@" + bot_me.username, '')
				if len(m.text.split(' ')) == 2:
					m.text = m.text.split(' ', 1)[1]
				else:
					for command in get_mp3_commands_array:
						m.text = m.text.replace(command, '')
					
				handle_youtube_link(m)
		except Exception:
			manage_exception(m, traceback.format_exc())
			

	while True:
		try:
			print "bot.polling"
			bot.polling(none_stop=True, interval=3)
		except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout) as e:
			print >> sys.stderr, str(e) + "\n"
			time.sleep(15) # used to avoid temporary errors
		except Exception as e:
			print >> sys.stderr, traceback.format_exc()
			for chat_id in users_db.get_root_chat_id():
				bot.send_message(chat_id, str(traceback.format_exc()))
			exit(1)


if __name__ == '__main__':	
	try:
		with open(settings.SECRETS_PATH, 'r') as f:
			settings.BOT_SECRETS["yt2audiobot_root"] = f.readline().strip()
			settings.BOT_SECRETS["telegram_token"] = f.readline().strip()
			settings.BOT_SECRETS["musixmatch_key"] = f.readline().strip()
			start_bot()
	except IOError as e:
		print e
		exit(1)
