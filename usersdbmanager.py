#!/usr/bin/env python
# -*- coding: utf-8 -*-

from peewee import *
import settings
import datetime


users_db = SqliteDatabase(settings.ABS_PATH_USERS_DB)



class TermColors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


class UserAlreadyException(Exception):
	def __init__(self, message):
		super(UserAlreadyException, self).__init__(message)


class UserBlockedException(Exception):
	def __init__(self, message):
		super(UserBlockedException, self).__init__(message)


DEFAULT_TELEGRAM_ID = 0
class AuthorizedUser(Model):
	telegram_id = IntegerField(default=DEFAULT_TELEGRAM_ID)
	first_name = CharField(default="")
	last_name = CharField(default="")
	username = CharField(default="")
	last_connection = DateField(default=datetime.datetime.now())
	blocked = BooleanField(default=False)
	
	def save(self, *args, **kwargs):
		self.last_connection = datetime.datetime.now()
		return super(AuthorizedUser, self).save(*args, **kwargs)
	
	class Meta:
		database = users_db


class Admin(Model):
	authorized_user = ForeignKeyField(AuthorizedUser, primary_key=True)
	chat_id	= IntegerField(default=0)
	
	class Meta:
		database = users_db

# http://stackoverflow.com/questions/951686/is-a-one-column-table-good-design
class Root(Model):
	admin = ForeignKeyField(Admin, primary_key=True)
	
	class Meta:
		database = users_db


class UsersDBController(object):
	def __init__(self):
		self.db = users_db
		self.db.connect()
		self.db.create_tables([AuthorizedUser, Admin, Root], safe=True)
		
		# initialization and checking root account
		root_username = settings.BOT_SECRETS["yt2audiobot_root"]		
		root_count = AuthorizedUser.select().where(AuthorizedUser.username == root_username).count()
		root_count += Admin.select().join(AuthorizedUser).where(AuthorizedUser.username == root_username).count()
		root_count += Root.select().join(Admin).join(AuthorizedUser).where(AuthorizedUser.username == root_username).count()
		
		if root_count != 3 and root_count != 0:
			user_answer = raw_input(TermColors.WARNING + "Warning:  root_count = " + str(root_count) + "\n"
				"Something went wrong in the database and seems to be missing the root user (or something else)!\n"
				"Need to drop all tables and recreate them all.\n\n"
				"Do you want to continue? [Type 'yes' to proceed]" + TermColors.ENDC)
			if user_answer == "yes":
				self.db.drop_tables([Root, Admin, AuthorizedUser], safe=True)
				self.db.create_tables([AuthorizedUser, Admin, Root], safe=True)
			else:
				exit(1)
		try:
			Root.select().join(Admin).join(AuthorizedUser).where(AuthorizedUser.username == root_username).get()
			print "Welcome " + root_username
		except Root.DoesNotExist:
			# reset of all database
			root_user = AuthorizedUser.create(first_name='Root', last_name='Root', username=root_username)
			root_admin = Admin.create(authorized_user=root_user)
			Root.create(admin=root_admin)
			print "Root " + root_username + " initialization completed!"
	
	def __predicate_telegram_id_and_username(self, telegram_id=None, username=None):
		if telegram_id == None and username == None:
			raise Exception("telegram_id and username are None!")
		telegram_id_predicate = (AuthorizedUser.telegram_id == telegram_id)
		username_predicate = (AuthorizedUser.username == username) & \
			(AuthorizedUser.telegram_id == DEFAULT_TELEGRAM_ID)
		return (telegram_id_predicate) | (username_predicate)
	
	def __authorized_users_select_query(self, get_all=False, **attributes):
		predicate = self.__predicate_telegram_id_and_username(**attributes)
		
		if get_all == True:
			return AuthorizedUser.select().where(predicate)
		else:
			return AuthorizedUser.select().where(
				(predicate) & (AuthorizedUser.blocked == False)
			)
			
	def __admin_select_query(self, **attributes):
		predicate = self.__predicate_telegram_id_and_username(**attributes)
		return Admin.select().join(AuthorizedUser).where(predicate)
	
	def user_exists(self, **attributes):
		return self.__authorized_users_select_query(get_all=True, **attributes).exists()
	
	def is_authorized(self, **attributes):
		return self.__authorized_users_select_query(**attributes).exists()
	
	def is_admin(self, **attributes):
		return self.__admin_select_query(**attributes).exists()
	
	def is_root(self, **attributes):
		predicate = self.__predicate_telegram_id_and_username(**attributes)
		return Root.select().join(Admin).join(AuthorizedUser).where(predicate).exists()
	
	def get_root_chat_id(self):
		q = Admin.select(Admin.chat_id).join(Root)
		return [admin.chat_id for admin in q]
	
	def search_authorized_user(self, get_all=False, **attributes):
		try:
			return self.__authorized_users_select_query(get_all=get_all, **attributes).get()
		except AuthorizedUser.DoesNotExist:
			return None
	
	def search_admin(self, **attributes):
		try:
			return self.__admin_select_query(**attributes).get()
		except Admin.DoesNotExist:
			return None
			
	def add_authorized_user(self, **attributes):
		if self.user_exists(**attributes):
			raise UserAlreadyException("User already exists")
		else:
			AuthorizedUser.create(**attributes)
	
	def add_admin(self, **attributes):
		if self.is_admin(**attributes):
			raise UserAlreadyException("User is already an admin")
		# search for authorized user.. if not exists then create it
		auth_user = self.search_authorized_user(get_all=True, **attributes)
		if auth_user is None:
			auth_user = AuthorizedUser.create(**attributes)
		elif auth_user.blocked:
			raise UserBlockedException("Trying to access to a blocked user")
		# create admin
		Admin.create(authorized_user=auth_user)