# yt2audiobot
### Telegram bot for converting YouTube videos to mp3!


#### Instructions:
* Use **/start** to begin (this will show you your ID) or **/help** to view all available commands.
* Just give me the YouTube link and I will send you back the mp3 converted from the video. :grin:
* Now **yt2audiobot** works either with the videos or the playlists! 

#### Installation:
```
# pip install -r requirements.txt
```
or you can use the script `setup_venv_and_db` to create a virtual environment for Python 2.7 and initialize the database


#### Configuration:
Create a file named `SECRETS.txt` in the root folder based of `EXAMPLE_SECRETS.txt`.. It needs to have the following lines:

1. Your telegram username so you can be the root of your bot and can add other users or admins
2. The bot access token! Get it simply by talking to [BotFather](https://telegram.me/botfather) and follow a few simple [steps](https://core.telegram.org/bots#6-botfather)
3. The musixmatch api key obtainable by registering at this [link](https://developer.musixmatch.com/)


#### Running:
Just use `./startstop` to run it or stop it. You can also add `start/stop` parameter.


#### Deploying:
I have created the `deploy` script to easily update the code on my server. If you want to use it, it is probably a great base but I think you will have to tune it for your needs..


#### Thanks to:
* eternnoir (https://github.com/eternnoir/pyTelegramBotAPI)
* rg3 (https://github.com/rg3/youtube-dl/)
* coleifer (https://github.com/coleifer/peewee)

for these amazing libraries. :heart:


#### TODO:
* I don't have so much time to work at this, so the code can be a bit ugly. As soon as I can I'll put my hands and time on this project.
* Merge the databases.. I don't even know why I created them separately by the first time! 
* Users management for root and admins → list, ban, etc.
* Audio management for root and admins → list, delete, etc.
* Increase of the usability.. Telegram updates incessantly!
* Make it works on Python 3.3+ at least!
* Think about moving to [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)
