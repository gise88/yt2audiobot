#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import os
import re
import utils
import settings
import youtube_dl as ytdl
import metadatahelper


class PlaylistArgumentError(ValueError):
	def __init__(self, message):
		super(PlaylistArgumentError, self).__init__(message)
		
class LimitDurationArgumentError(ValueError):
	def __init__(self, message):
		super(LimitDurationArgumentError, self).__init__(message)
		
class DownloadError(ValueError):
	def __init__(self, message):
		super(DownloadError, self).__init__(message)

class YTHelper(object):
	
	def __init__(self):
		self.REGEX_MATCH_PLAYLIST = "(/playlist\?)"

		self.INFO_OPTS = {
			#'verbose': True,
			'logger': self,
			'socket_timeout': 3
		}

		self.DOWNLOAD_VIDEO_AND_CONVERT_TO_MP3_OPTS = {
			#'verbose': True,
			'outtmpl': settings.OUTPUT_FORMAT,
			'format': 'bestaudio/best',
			'socket_timeout': 3,
			#'keepvideo': True,
			'postprocessors': [{
				'key': 'FFmpegExtractAudio',
				'preferredcodec': settings.PREFERRED_AUDIO_CODEC,
				'preferredquality': '192',
			}],
			'logger': self,
			'progress_hooks': [self.progress_hook],
		}

		self.PRINTABLE_INFO = {
			"creator",
			"duration",
			"id",
			"title",
			"ext",
			"categories",
			"tags",
			"uploader",
			"alt_title",
			"url",
			"webpage_url",
			"formats"
		}
	
	def debug(self, msg):
		#print "[def debug]" + str(msg)
		pass

	def warning(self, msg):
		#print "[def warning]" + str(msg)
		pass

	def error(self, msg):
		print "[def error]" + str(msg)

	def progress_hook(self, d):
		pass
	
	def get_file_abspath(self, filename):
		return os.path.abspath(os.path.join(settings.AUDIO_OUTPUT_DIR, filename))
	
	def process_request(self, url, ydl, download=True):
		if ydl:
			# make sure that the URL is not in a playlist or this procedure will download everything
			if re.search(self.REGEX_MATCH_PLAYLIST, url):
				raise PlaylistArgumentError('Playlist are not yet supported.')
			
			result = ydl.extract_info( url, download=download )
			
			if 'entries' in result:
				# Can be a playlist or a list of videos
				raise PlaylistArgumentError('Playlist are not yet supported.')
			else:
				# Just a video
				video = result
			return video
		
	def extract_video_info(self, url):
		ydl = ytdl.YoutubeDL(self.INFO_OPTS)
		info = self.process_request(url, ydl, download=False)
		info["title"] = info["title"].encode('ascii', 'ignore')
		info["description"] = info["description"].encode('ascii', 'ignore')
		return info

	def download_video_and_convert(self, url):
		info = self.extract_video_info(url)
		if info["duration"] >= settings.LIMIT_VIDEO_DURATION:
			raise LimitDurationArgumentError('Video is too long.')
		
		ydl = ytdl.YoutubeDL(self.DOWNLOAD_VIDEO_AND_CONVERT_TO_MP3_OPTS)
		info = self.process_request(url, ydl)
		data = {
			"title": info["title"],
			"filename": self.get_file_abspath(info["id"] + "." + settings.PREFERRED_AUDIO_CODEC)
		}
		return data
	
	def clean_link(self, url):
		
		# A YouTube video URL may be encountered in a variety of formats so a regex is needed to get the video id
		
		# Need to clean link like the following one because with this form can return error 
		# https://www.youtube.com/watch?v=a01QQZyl-_I&index=1&list=PLJ8y7DDcrI_p8LixOD4nVgrr9P6f4n2Lv
		
		# thanks to http://stackoverflow.com/a/17030234
		regex = "(?:http(?:s)?:\/\/)?(?:www\.)?(?:m\.)?(?:youtu\.be\/|youtube\.com\/(?:(?:watch)?\?(?:.*&)?v(?:i)?=|(?:embed|v|vi)\/))([^\?&\"'>]+)"

		# the previous regex supports the following urls
		#links = [
		#	"http://youtu.be/NLqAF9hrVbY",
		#	"http://www.youtube.com/embed/NLqAF9hrVbY",
		#	"https://www.youtube.com/embed/NLqAF9hrVbY",
		#	"http://www.youtube.com/v/NLqAF9hrVbY?fs=1&hl=en_US",
		#	"http://www.youtube.com/watch?v=NLqAF9hrVbY",
		#	"http://www.youtube.com/watch?v=JYArUl0TzhA&feature=featured",
		#	"https://www.youtube.com/watch?v=a01QQZyl-_I&index=1&list=PLJ8y7DDcrI_p8LixOD4nVgrr9P6f4n2Lv",
		#	"https://youtu.be/a01QQZyl-_I?list=PLJ8y7DDcrI_p8LixOD4nVgrr9P6f4n2Lv",
		#	# errors
		#	"https://www.youube.com/watch?v=qy1Fzem7mqA",
		#	"https://www.youtube.com/playlist?list=PL5jc9xFGsL8E12so1wlMS0r0hTQoJL74M",
		#]
		
		m = re.search(regex, url)
		if m is not None:
			youtube_id = m.group(1)
			return ("http://www.youtube.com/watch?v=" + str(youtube_id), youtube_id)
		else:
			return (url, None)
		
	def process_link(self, url):
		try:
			data = self.download_video_and_convert(url)
			metadata = metadatahelper.metadata_from_title(data["title"])			
			data["title"] = metadata.title
			data["author"] = metadata.author
			data["album"] = metadata.album
			data["track_number"] = metadata.track_number
			data["first_release_date"] = metadata.first_release_date
			
			data["filename"] = utils.rename_file(data["filename"], metadata.to_filename())
			
			return data
		except ytdl.utils.DownloadError as e:
			raise DownloadError(str(e))
