# JokeBot
Joke bot for matrix.org.
Old. Use [MpyBot](https://github.com/lugino-emeritus/MpyBot) as replacement.

## Controlling bot / get a joke
* Depending on the settings, just invite the bot (there is no public bot at the moment) to a room. Then it would join the room.
* Type `!joke` to get a joke (at the moment only german, pull requests welcome!).
* With `!joke language` you will get a joke in the language you defined (e.g. `en` or `de`).
* `!joke language type` would use a different joke generater if available.

Admin-tools (for users defined in the config-file in the admin_ids list):
* `!jokectl join room_id` would join a room (if possible).
* `!jokectl leave room_id` would leave a room (if possible). The room_id could be `this` to leave the current room

## Run your own joke bot
#### Requirements:
* matrix_client
* bs4 (BeatifulSoup)
* yaml
#### Start the bot:
First define your preferences in config.yaml. To start the bot use the command `python3 -m jb_main` in the folder JokeBot. (Bot tested with python 3.5)
