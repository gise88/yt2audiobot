#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals, absolute_import

import os
import logging
import requests
import youtube_dl as ytdl

from yt2audiobot import utils
from yt2audiobot import settings
from yt2audiobot import metadatahelper


logger = logging.getLogger(settings.BOT_NAME)


# PRINTABLE_INFO = {
#     'creator',
#     'duration',
#     'id',
#     'title',
#     'ext',
#     'categories',
#     'tags',
#     'uploader',
#     'alt_title',
#     'url',
#     'webpage_url',
#     'formats',
#     'extractor'
# }

def init_spotify():
    metadatahelper.spotifyhelper.Spotify.authenticate()


class FileIsTooLargeException(ValueError):
    pass


class DownloadError(ValueError):
    pass


class YoutubeDLLogger(object):
    def debug(self, msg):
        # logger.debug('[def debug] %s', msg)
        pass
    
    
    def warning(self, msg):
        # logger.warning('[def warning] %s', msg)
        pass
    
    
    def error(self, msg):
        logger.error('[def error] %s', msg)


class YoutubeVideo(object):
    YOUTUBE_WATCH_URL = 'https://www.youtube.com/watch?v=%s'
    
    
    def __str__(self):
        return ('%s (%s)' % (self.get_video_title(), self.get_url())).encode('utf8', 'replace')
    
    
    def __init__(self, video_id, info, progress_hook):
        self._DOWNLOAD_VIDEO_AND_EXTRACT_AUDIO = {
            'outtmpl': settings.OUTPUT_FORMAT,
            'format': 'bestaudio/best',
            'socket_timeout': 10,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': settings.PREFERRED_AUDIO_CODEC,
                'preferredquality': '192',
            }],
            'retries': 10,
            'logger': YoutubeDLLogger(),
            'progress_hooks': [self._private_progress_hook],
            'prefer_ffmpeg': True
        }
        
        self._video_id = video_id
        self._info = info
        self._progress_hook = progress_hook
    
    
    def _private_progress_hook(self, hook):
        self._progress_hook(hook, youtube_video=self)
    
    
    def get_url(self):
        return self.YOUTUBE_WATCH_URL % self._video_id
    
    
    def get_type(self):
        return self._info['extractor']
    
    
    def get_youtube_id(self):
        return self._video_id
    
    
    def get_video_title(self):
        return self._info['title']
    
    
    def get_video_thumbnails(self):
        return map(lambda x: x['url'], self._info['thumbnails'])
    
    
    def download_thumbnail(self, index):
        thumbnail = self.get_video_thumbnails()[index]
        output = os.path.abspath(os.path.join(settings.AUDIO_OUTPUT_DIR, 'thumb_{0}'.format(self.get_youtube_id())))
        
        r = requests.get(thumbnail, stream=True)
        if r.status_code == 200:
            with open(output, 'wb') as f:
                for chunk in r:
                    f.write(chunk)
        
        class Thumbnail(object):
            def __init__(self, url, filename, mimetype):
                self.url = url
                self.filename = filename
                self.mimetype = mimetype
        
        return Thumbnail(thumbnail, output, r.headers['Content-Type'])
    
    
    def is_part_of_playlist(self):
        return self._info['playlist_index'] is not None
    
    
    def _get_downloaded_file_abspath(self):
        filename = self.get_youtube_id() + '.' + settings.PREFERRED_AUDIO_CODEC
        return os.path.abspath(os.path.join(settings.AUDIO_OUTPUT_DIR, filename))
    
    
    def download_video_and_extract_audio(self):
        logger.info('Starting download: %s (%s)', self.get_video_title(), self.get_url())
        try:
            ydl = ytdl.YoutubeDL(self._DOWNLOAD_VIDEO_AND_EXTRACT_AUDIO)
            ydl.download([self.get_url()])
            
            self._progress_hook({
                'status': 'searching_metadata'
            }, youtube_video=self)
            
            metadata = metadatahelper.metadata_from_title(self.get_video_title())
            
            logger.debug(self._get_downloaded_file_abspath())
            logger.debug('{0}_{1}'.format(metadata.to_filename(), self.get_youtube_id()))
            
            filename = utils.rename_file(self._get_downloaded_file_abspath(),
                                         '{0}_{1}'.format(metadata.to_filename(), self.get_youtube_id()))
            
            # if the extracted audio file is larger than 50M
            filesize = os.path.getsize(filename)
            if filesize >> 20 > 50:
                raise FileIsTooLargeException(
                    'I am sorry. Telegram bots can currently send files of any type of up to 50 MB in size. '
                    'https://core.telegram.org/bots/faq#how-do-i-upload-a-large-file\n '
                    'This audio file is %s!' % utils.format_size(filesize))

            thumbnail = self.download_thumbnail(-1) if len(self.get_video_thumbnails()) > 0 else None
            metadatahelper.write_metadata(metadata, filename, thumbnail)
            os.remove(thumbnail.filename)
            
            return {
                'title': metadata.title,
                'author': metadata.author,
                'album': metadata.album,
                'track_number': metadata.track_number,
                'first_release_date': metadata.first_release_date,
                'filename': filename
            }
        except ytdl.utils.DownloadError as e:
            raise DownloadError('Failed downloading video: %s\n%s' % (self.__str__(), e))


class YTHelper(object):
    def __init__(self, url, progress_hook):
        self._url = url
        self._progress_hook = progress_hook
        self._INFO_OPTS = {
            'logger': YoutubeDLLogger(),
            'socket_timeout': 10
        }
        
        ydl = ytdl.YoutubeDL(self._INFO_OPTS)
        self._progress_hook({
            'status': 'getting_information'
        })
        self._info = ydl.extract_info(self._url, download=False)
        self._progress_hook({
            'status': 'information_downloaded',
            'type': 'playlist' if self.is_playlist() else 'video'
        })
    
    
    def get_info(self):
        return self._info
    
    
    def get_type(self):
        return self._info['extractor']
    
    
    def get_youtube_id(self):
        return self._info['id']
    
    
    def is_playlist(self):
        if 'playlist' in self.get_type():
            return True
        return False
    
    
    def manage_url(self):
        if not self.is_playlist():
            yield YoutubeVideo(self.get_youtube_id(), self.get_info(), self._progress_hook)
        else:
            for entry in self.get_info()['entries']:
                yield YoutubeVideo(entry['id'], entry, self._progress_hook)


if __name__ == '__main__':
    links = [
        'https://www.youtube.com/shared?ci=teeR9PxnJG0',
        'https://www.youtube.com/watch?v=PDSkFeMVNFs',
        'https://www.youtube.com/watch?v=FfbZfBk-3rI',
        'https://www.youtube.com/playlist?list=PL5jc9xFGsL8E12so1wlMS0r0hTQoJL74M',
        'https://www.youtube.com/watch?v=LL8wkskDlbs&index=1&list=PL5jc9xFGsL8E12so1wlMS0r0hTQoJL74M',
        'https://www.youtube.com/watch?v=wGyUP4AlZ6I',
        'https://www.youtube.com/watch?v=ytWz0qVvBZ0',
        'https://www.youtube.com/playlist?list=PL7E7D54D2B79C2D41',
        'http://youtu.be/NLqAF9hrVbY',
        'https://www.youtube.com/shared?ci=teeR9PxnJG0',
        'http://www.youtube.com/embed/NLqAF9hrVbY',
        'https://www.youtube.com/embed/NLqAF9hrVbY',
        'http://www.youtube.com/v/NLqAF9hrVbY?fs=1&hl=en_US',
        'http://www.youtube.com/watch?v=NLqAF9hrVbY',
        'http://www.youtube.com/watch?v=JYArUl0TzhA&feature=featured',
        'https://www.youtube.com/watch?v=a01QQZyl-_I&index=1&list=PLJ8y7DDcrI_p8LixOD4nVgrr9P6f4n2Lv',
        'https://youtu.be/a01QQZyl-_I?list=PLJ8y7DDcrI_p8LixOD4nVgrr9P6f4n2Lv',
        'https://www.youtube.com/watch?v=LL8wkskDlbs&index=1&list=PL5jc9xFGsL8E12so1wlMS0r0hTQoJL74M',
        # errors
        'https://www.youube.com/watch?v=qy1Fzem7mqA',
        'https://www.youtube.com/playlist?list=PL5jc9xFGsL8E12so1wlMS0r0hTQoJL74M',
    ]
