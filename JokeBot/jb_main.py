import requests
import matrix_client
from matrix_client.client import MatrixClient
from bs4 import BeautifulSoup
import time
from datetime import datetime
import yaml
import threading
import logging

logging.basicConfig(level=logging.DEBUG, format='%(levelname)-8s %(asctime)s: %(message)s')
logging.getLogger(matrix_client.client.__name__).setLevel(logging.DEBUG)
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

CONFIG_FILENAME = 'config.yaml'

def load_yaml_config(filename):
	with open(filename, 'r') as conf_file:
		return yaml.load(conf_file)

config_dic = load_yaml_config(CONFIG_FILENAME)
if 'default_joke' in config_dic:
	DEFAULT_LANGUAGE = config_dic['default_joke'].get('language', 'de')
	DEFAULT_TYPE = config_dic['default_joke'].get('type', '0')
else:
	DEFAULT_LANGUAGE = 'de'
	DEFAULT_TYPE = '0'

def get_joke(language=DEFAULT_LANGUAGE, type_=DEFAULT_TYPE):
	# pull requsts for this method are really welcome
	try:
		if language == 'de':
			if type_ == '0':
				data = requests.get('http://www.witze.net/?embed&image=none&menu=off', timeout=30).text
				soup = BeautifulSoup(data, 'html.parser')
				x = [el for el in soup.findAll(text=True) if el.parent.name not in ['style', 'head', 'title']]
				return '\n'.join(x)
			elif type_ == 'foo':
				return 'bar'
		elif language == 'en':
			if type_ == '0':
				pass
		return "Settings (language = {}, type_ = {}) are not available yet.".format(language, type_)
	except Exception as e:
		return "Something went wrong while receiving joke: {}".format(repr(e))

class JokeBot:
	bot_startcmd = '!joke'
	bot_display_name = 'JokeBot'
	auto_join_invited_rooms = True
	mcl = None
	init_done = False
	admin_ids = set()

	def __init__(self, filename=CONFIG_FILENAME):
		logging.debug('load config')
		config_dic = load_yaml_config(filename)
		matrix_server = config_dic['matrix_server']
		login_with_token = False
		if matrix_server.get('token', ''):
			if not matrix_server.get('user_id', ''):
				matrix_server['user_id'] = config_dic['matrix_user']['username']
			login_with_token = True
		else:
			matrix_user = config_dic['matrix_user']

		bot_startcmd = config_dic.get('bot_startcmd')
		if bot_startcmd:
			self.bot_startcmd = bot_startcmd
		bot_display_name = config_dic.get('bot_display_name')
		if bot_display_name:
			self.bot_display_name = bot_display_name
		self.auto_join_invited_rooms = config_dic.get('auto_join_invited_rooms', True)
		self.admin_ids = set(config_dic.get('admin_ids', []))

		logging.debug('init bot')

		if login_with_token:
			logging.debug('init bot with token')
			self.mcl = MatrixClient(**matrix_server)
		else:
			logging.debug('init bot with password')
			self.mcl = MatrixClient(**matrix_server)
			self.mcl.login_with_password_no_sync(**matrix_user)

		m_user = self.mcl.get_user(self.mcl.user_id)
		if m_user.get_display_name() != self.bot_display_name:
			m_user.set_display_name(self.bot_display_name)

		self.mcl.add_invite_listener(self.process_invite)
		self.mcl.add_listener(self.process_message, 'm.room.message')

		self.init_done = True
		logging.info('bot initialization successful')

	def run(self):
		if self.init_done:
			logging.debug('run listen_forever')
			self.mcl.listen_forever()
		else:
			logging.warning('bot not initialized successful')

	def join_room(self, room_id):
		self.ignore_room_temporary(room_id) # necessary while joining room because otherwise old messages would be processed
		try:
			logging.info('joining new room {}'.format(room_id))
			room = self.mcl.join_room(room_id)
			room.send_text("Welcome! I'm a joke bot. Type '{}' and I will tell you a joke.".format(self.bot_startcmd))
			return True
		except:
			logging.exception('Exception while joining room {}'.format(room_id))
			return False

	temp_ignored_rooms = set()

	def temp_ignore_room_thread(self, room_id):
		logging.debug('temporary ignoring room {}'.format(room_id))
		self.temp_ignored_rooms.add(room_id)
		time.sleep(10)
		self.temp_ignored_rooms.remove(room_id)
		logging.debug('not ignoring room {} any more'.format(room_id))

	def ignore_room_temporary(self, room_id):
		threading.Thread(target=self.temp_ignore_room_thread, args=[room_id], daemon=True).start()

	def leave_room(self, room_id):
		logging.debug('trying to leave room with id {}'.format(room_id))
		leave_room = self.mcl.get_rooms().get(room_id, '')
		if not leave_room:
			logging.debug('bot not in room with id {}'.format(room_id))
			return False
		if leave_room.leave():
			logging.debug('leaving room {} was successful'.format(room_id))
			return True
		else:
			logging.debug('failed to leave known room with id {}'.format(leave_room.room_id))
		return False

	def process_invite(self, room_id, state=None):
		logging.debug('received invitation of {}'.format(room_id))
		if self.auto_join_invited_rooms:
			self.join_room(room_id)

	def evaluate_bot_message(self, room, sender, msg):
		if msg.startswith('ctl'):
			logging.debug("received control message '{}' in room '{}'".format(msg, room.room_id))
			if sender not in self.admin_ids:
				logging.debug('{} has no permissions to send a ctl-message'.format(sender))
				room.send_notice('{} has no permissions to send a ctl-message'.format(sender))
				return
			data = msg.split(' ')[1:]
			if len(data) == 2:
				if data[0] == 'join':
					if not self.join_room(data[1]):
						room.send_notice('something went wrong while joining room')
				elif data[0] == 'leave':
					if data[1] == 'this':
						data[1] = room.room_id
					if not self.leave_room(data[1]):
						room.send_notice('room could not be left')
			return

		logging.info('sending joke to room {}'.format(room.room_id))
		answer = '...'
		data = msg.split(' ')[1:] # remove first empty string
		if len(data) == 0:
			answer = get_joke()
		elif len(data) == 1:
			answer = get_joke(data[0])
		elif len(data) == 2:
			answer = get_joke(data[0], data[1])
		logging.debug('starting room send text')
		room.send_text(answer)
		logging.debug('done room send text')


	def process_message(self, roomchunk):
		if roomchunk['sender'] == self.mcl.user_id:
			return

		if roomchunk['room_id'] in self.temp_ignored_rooms:
			logging.debug('ignoring room {} temporary'.format(roomchunk['room_id']))
			return

		content = roomchunk['content']
		if content['msgtype'] == 'm.text':
			msg = content['body']
			if msg.startswith(self.bot_startcmd):
				room = self.mcl.get_rooms()[roomchunk['room_id']]
				msg = msg[len(self.bot_startcmd):]
				self.evaluate_bot_message(room, roomchunk['sender'], msg)


sleeping_time = 5
timestamp_last_exception = time.time()
while True:
	try:
		jokebot = JokeBot()
		jokebot.run()
	except:
		logging.exception('Exception at time {}'.format(datetime.now()))

	if time.time() - timestamp_last_exception > 900: # 15 min
		sleeping_time = 5
	elif sleeping_time < 450:
		sleeping_time = int(sleeping_time * 4/3 + 1)
	else:
		sleeping_time = 600
	timestamp_last_exception = time.time()
	time.sleep(sleeping_time)
