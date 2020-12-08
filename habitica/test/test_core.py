import unittest, unittest.mock
unittest.defaultTestLoader.testMethodPrefix = 'should'
from collections import namedtuple
from .. import core, api, timeutils

class MockRequest:
	def __init__(self, method, path, response, cached=False):
		self.method = method
		self.path = path
		self.response = api.dotdict(response) if type(response) is dict else response
		self.params = None
		self.body = None
		self.cached = cached

class MockAPI:
	""" /content call is cached. """
	def __init__(self, *requests):
		self.base_url = 'http://localhost'
		self.requests = list(requests)
		self.responses = []
		self.cache = [
			MockRequest('get', ['content'], {'data': {
				'potion' : {
					'text' : 'Health Potion',
					'notes' : 'Heals 15 hp',
					'type' : 'potion',
					'key' : 'HealthPotion',
					'value' : 25,
					},
				'quests' : {
					'mycollectquest' : {
						'text' : 'Collect N items',
						'collect' : {
							'item1' : {
								'count' : 40,
								},
							'item2' : {
								'count' : 60,
								},
							},
						},
					'mybossquest' : {
						'text' : 'Slay Boss',
						'boss' : {
							'hp' : 200,
							},
						},
					},
				'petInfo': {
					'Fox' : {
						'text' : 'Fox',
						},
					},
				'mountInfo': {
					'Wolf' : {
						'text' : 'Wolf',
						},
					},
				}}, cached=True),
			]
	def cached(self, *args, **kwargs):
		return self
	def _perform_request(self, method, path, params=None, body=None):
		for _ in self.cache:
			if _.method == method and list(_.path) == list(path):
				return _.response

		request = None
		for _ in self.requests:
			if _.method == method and list(_.path) == list(path):
				request = _
				break
		assert request is not None, "Expected request is not found in mock request chain: {0} /{1}".format(method.upper(), '/'.join(path))
		self.requests.remove(request)
		request.params = params
		request.body = body
		self.responses.append(request)
		if request.cached: # pragma: no cover
			self.cache.append(request)
		return request.response
	def get(self, *path, **params):
		return self._perform_request('get', path, params=params)
	def post(self, *path, _body=None, **params):
		return self._perform_request('post', path, params=params, body=_body)
	def put(self, *path, _body=None, **params):
		return self._perform_request('put', path, params=params, body=_body)
	def delete(self, *path, **params):
		return self._perform_request('delete', path, params=params)

class TestBaseHabitica(unittest.TestCase):
	def should_get_home_url(self):
		habitica = core.Habitica(_api=MockAPI())
		self.assertEqual(habitica.home_url(), 'http://localhost/#/tasks')
	def should_detect_working_server(self):
		habitica = core.Habitica(_api=MockAPI(
			MockRequest('get', ['status'], {'data': {'status': 'up'}}),
			MockRequest('get', ['status'], {'data': {'status': ''}}),
			))
		self.assertTrue(habitica.server_is_up())
		self.assertFalse(habitica.server_is_up())
	def should_retrieve_and_cache_content(self):
		habitica = core.Habitica(_api=MockAPI(
			))
		content = habitica.content
		content.my_value = 'foo'
		content = habitica.content
		self.assertEqual(content.my_value, 'foo')
	def should_get_user_proxy_without_calls(self):
		habitica = core.Habitica(_api=MockAPI(
			))
		user = habitica.user
	def should_get_user_directly_via_proxy(self):
		habitica = core.Habitica(_api=MockAPI(
			MockRequest('get', ['user'], {'data': {'name': '...'}}),
			))
		user = habitica.user()
	def should_get_groups(self):
		habitica = core.Habitica(_api=MockAPI(
			MockRequest('get', ['groups'], {'data': [
				{'name' : 'Party'},
				{'name' : 'My Guild'},
				]}),
			))
		groups = habitica.groups(core.Group.PARTY, core.Group.GUILDS)
		self.assertEqual(len(groups), 2)
		self.assertEqual(groups[0].name, 'Party')
		self.assertEqual(groups[1].name, 'My Guild')

class TestChallenges(unittest.TestCase):
	def _challenge(self):
		return MockRequest('get', ['challenges', 'groups', 'group1'], {'data': [{
			'id' : 'chlng1',
			'name' : 'Create Habitica API tool',
			'shortName' : 'HabiticaAPI',
			'summary' : 'You have to create Habitica API tool',
			'createdAt' : 1600000000,
			'updatedAt' : 1600000000,
			'prize' : 4,
			'memberCount' : 2,
			'official' : False,
			'leader' : 'person1',
			'group' : {
				'id': 'group1',
				'name': 'Party',
				},
			'tasksOrder' : {
				'rewards' : ['reward1'],
				'todos' : ['todo1'],
				'dailys' : ['daily1'],
				'habits' : ['habit1'],
				},
			}]})
	def should_fetch_challenge(self):
		habitica = core.Habitica(_api=MockAPI(
			MockRequest('get', ['groups'], {'data': [{
					'name' : 'Party',
					'id' : 'group1',
					}]}),
			self._challenge(),
			MockRequest('get', ['tasks', 'reward1'], {'data': {
				'text' : 'Use API tool',
				}}),
			MockRequest('get', ['tasks', 'todo1'], {'data': {
				'text' : 'Complete API tool',
				}}),
			MockRequest('get', ['tasks', 'daily1'], {'data': {
				'text' : 'Add feature',
				}}),
			MockRequest('get', ['tasks', 'habit1'], {'data': {
				'text' : 'Write better code',
				}}),
			))
		party = habitica.groups(core.Group.PARTY)[0]
		challenge = party.challenges()[0]
		self.assertEqual(challenge.id, 'chlng1')
		self.assertEqual(challenge.name, 'Create Habitica API tool')
		self.assertEqual(challenge.shortName, 'HabiticaAPI')
		self.assertEqual(challenge.createdAt, 1600000000)
		self.assertEqual(challenge.updatedAt, 1600000000)
		self.assertEqual(challenge.prize, 4)
		self.assertEqual(challenge.memberCount, 2)
		self.assertFalse(challenge.official)
		self.assertEqual(challenge.leader(), 'person1')

		group = challenge.group()
		self.assertEqual(group.id, party.id)
		self.assertEqual(group.name, party.name)

		rewards = challenge.rewards()
		self.assertEqual(rewards[0].text, 'Use API tool')
		todos = challenge.todos()
		self.assertEqual(todos[0].text, 'Complete API tool')
		dailies = challenge.dailies()
		self.assertEqual(dailies[0].text, 'Add feature')
		habits = challenge.habits()
		self.assertEqual(habits[0].text, 'Write better code')
	def should_get_challenge_data_as_csv(self):
		habitica = core.Habitica(_api=MockAPI(
			MockRequest('get', ['groups'], {'data': [{
					'name' : 'Party',
					'id' : 'group1',
					}]}),
			self._challenge(),
			MockRequest('get', ['challenges', 'chlng1', 'export', 'csv'], 'AS CSV'),
			))
		party = habitica.groups(core.Group.PARTY)[0]
		challenge = party.challenges()[0]
		self.assertEqual(challenge.as_csv(), 'AS CSV')
	def should_clone_challenge(self):
		habitica = core.Habitica(_api=MockAPI(
			MockRequest('get', ['groups'], {'data': [{
					'name' : 'Party',
					'id' : 'group1',
					}]}),
			self._challenge(),
			MockRequest('post', ['challenges', 'chlng1', 'clone'], {'challenge': {
				'id' : 'chlng2',
				'name' : 'Create Habitica API tool',
				'shortName' : 'HabiticaAPI',
				}})
			))
		party = habitica.groups(core.Group.PARTY)[0]
		challenge = party.challenges()[0]
		challenge = challenge.clone()
		self.assertEqual(challenge.id, 'chlng2')
		self.assertEqual(challenge.name, 'Create Habitica API tool')
		self.assertEqual(challenge.shortName, 'HabiticaAPI')
	def should_update_challenge(self):
		habitica = core.Habitica(_api=MockAPI(
			MockRequest('get', ['groups'], {'data': [{
					'name' : 'Party',
					'id' : 'group1',
					}]}),
			self._challenge(),
			MockRequest('put', ['challenges', 'chlng1'], {'data': {
				'id' : 'chlng1',
				'name' : 'Develop Habitica API tool',
				'shortName' : 'API',
				'summary' : 'Go and create Habitica API tool',
				}})
			))
		party = habitica.groups(core.Group.PARTY)[0]
		challenge = party.challenges()[0]
		challenge.update()
		self.assertEqual(challenge.name, 'Create Habitica API tool')
		self.assertEqual(challenge.shortName, 'HabiticaAPI')
		self.assertEqual(challenge.summary, 'You have to create Habitica API tool')
		challenge.update(
				name = 'Develop Habitica API tool',
				summary = 'API',
				description = 'Go and create Habitica API tool',
				)
		self.assertEqual(challenge.name, 'Develop Habitica API tool')
		self.assertEqual(challenge.shortName, 'API')
		self.assertEqual(challenge.summary, 'Go and create Habitica API tool')
	def should_join_challenge(self):
		habitica = core.Habitica(_api=MockAPI(
			MockRequest('get', ['groups'], {'data': [{
					'name' : 'Party',
					'id' : 'group1',
					}]}),
			self._challenge(),
			MockRequest('post', ['challenges', 'chlng1', 'join'], {'data': {
					'id' : 'chlng1',
					'memberCount' : 3,
					}}),
			MockRequest('post', ['challenges', 'chlng1', 'leave'], {'data': {
					}}),
			))
		party = habitica.groups(core.Group.PARTY)[0]
		challenge = party.challenges()[0]
		challenge.join()
		self.assertEqual(challenge.memberCount, 3)
		challenge.leave()
		self.assertEqual(challenge.api.responses[-1].path[-1], 'leave')
	def should_select_winner(self):
		habitica = core.Habitica(_api=MockAPI(
			MockRequest('get', ['groups'], {'data': [{
					'name' : 'Party',
					'id' : 'group1',
					}]}),
			self._challenge(),
			MockRequest('post', ['challenges', 'chlng1', 'selectWinner', 'person1'], {'data': {
					}}),
			))
		party = habitica.groups(core.Group.PARTY)[0]
		challenge = party.challenges()[0]
		Person = namedtuple('Person', 'id name')
		challenge.selectWinner(Person('person1', 'Name'))
		self.assertEqual(challenge.api.responses[-1].path[-2:], ['selectWinner', 'person1'])
	def should_delete_challenge(self):
		habitica = core.Habitica(_api=MockAPI(
			MockRequest('get', ['groups'], {'data': [{
					'name' : 'Party',
					'id' : 'group1',
					}]}),
			self._challenge(),
			MockRequest('delete', ['challenges', 'chlng1'], {'data': {
					}}),
			))
		party = habitica.groups(core.Group.PARTY)[0]
		challenge = party.challenges()[0]
		challenge.delete()
		self.assertEqual(challenge.api.responses[-1].method, 'delete')
		self.assertEqual(challenge.api.responses[-1].path[-1], 'chlng1')

class TestChat(unittest.TestCase):
	def should_fetch_messages(self):
		habitica = core.Habitica(_api=MockAPI(
			MockRequest('get', ['groups'], {'data': [{
					'name' : 'Party',
					'id' : 'group1',
					}]}),
			MockRequest('get', ['groups', 'group1', 'chat'], {'data': [{
					'id' : 'chat1',
					'user' : 'person1',
					'timestamp' : 1600000000,
					'text' : 'Hello',
					},{
					'id' : 'chat2',
					'user' : 'person2',
					'timestamp' : 1600001000,
					'text' : 'Hello back',
					}]}),
			))

		party = habitica.groups(core.Group.PARTY)[0]
		messages = party.chat()
		self.assertEqual(messages[0].id, 'chat1')
		self.assertEqual(messages[0].timestamp, 1600000000)
		self.assertEqual(messages[0].user, 'person1')
		self.assertEqual(messages[0].text, 'Hello')
		self.assertEqual(messages[1].id, 'chat2')
		self.assertEqual(messages[1].timestamp, 1600001000)
		self.assertEqual(messages[1].user, 'person2')
		self.assertEqual(messages[1].text, 'Hello back')
	def should_flag_message(self):
		habitica = core.Habitica(_api=MockAPI(
			MockRequest('get', ['groups'], {'data': [{
					'name' : 'Party',
					'id' : 'group1',
					}]}),
			MockRequest('get', ['groups', 'group1', 'chat'], {'data': [{
					'id' : 'chat1',
					'user' : 'person1',
					'timestamp' : 1600000000,
					'text' : 'Hello',
					}]}),
			MockRequest('post', ['groups', 'group1', 'chat', 'chat1', 'flag'], {'data': {
					'id' : 'chat1',
					'user' : 'person1',
					'timestamp' : 1600000000,
					'text' : 'Hello',
					'flagged' : True,
					}}),
			))

		party = habitica.groups(core.Group.PARTY)[0]
		message = party.chat()[0]
		message.flag(comment='Yazaban!')
		self.assertTrue(message._data['flagged'])
	def should_clear_message_from_flags(self):
		habitica = core.Habitica(_api=MockAPI(
			MockRequest('get', ['groups'], {'data': [{
					'name' : 'Party',
					'id' : 'group1',
					}]}),
			MockRequest('get', ['groups', 'group1', 'chat'], {'data': [{
					'id' : 'chat1',
					'user' : 'person1',
					'timestamp' : 1600000000,
					'text' : 'Hello',
					}]}),
			MockRequest('post', ['groups', 'group1', 'chat', 'chat1', 'clearflags'], {'data': {
					}}),
			))

		party = habitica.groups(core.Group.PARTY)[0]
		message = party.chat()[0]
		message.clearflags()
	def should_like_message(self):
		habitica = core.Habitica(_api=MockAPI(
			MockRequest('get', ['groups'], {'data': [{
					'name' : 'Party',
					'id' : 'group1',
					}]}),
			MockRequest('get', ['groups', 'group1', 'chat'], {'data': [{
					'id' : 'chat1',
					'user' : 'person1',
					'timestamp' : 1600000000,
					'text' : 'Hello',
					}]}),
			MockRequest('post', ['groups', 'group1', 'chat', 'chat1', 'like'], {'data': {
					'id' : 'chat1',
					'user' : 'person1',
					'timestamp' : 1600000000,
					'text' : 'Hello',
					'liked' : 1,
					}}),
			))

		party = habitica.groups(core.Group.PARTY)[0]
		message = party.chat()[0]
		message.like()
		self.assertEqual(message._data['liked'], 1)
	def should_mark_messages_as_read(self):
		habitica = core.Habitica(_api=MockAPI(
			MockRequest('get', ['groups'], {'data': [{
					'name' : 'Party',
					'id' : 'group1',
					}]}),
			MockRequest('post', ['groups', 'group1', 'chat', 'seen'], {'data': [
					]}),
			))

		party = habitica.groups(core.Group.PARTY)[0]
		party.chat.mark_as_read()
	def should_delete_messages(self):
		habitica = core.Habitica(_api=MockAPI(
			MockRequest('get', ['groups'], {'data': [{
					'name' : 'Party',
					'id' : 'group1',
					}]}),
			MockRequest('delete', ['groups', 'group1', 'chat', 'chat1'], {'data': [{
					}]}),
			MockRequest('get', ['groups', 'group1', 'chat'], {'data': [{
					'id' : 'chat1',
					'user' : 'person1',
					'timestamp' : 1600000000,
					'text' : 'Hello',
					}]}),
			MockRequest('delete', ['groups', 'group1', 'chat', 'chat1'], {'data': [{
					'id' : 'chat2',
					'user' : 'person2',
					'timestamp' : 1600001000,
					'text' : 'Hello back',
					}]}),
			))

		party = habitica.groups(core.Group.PARTY)[0]
		chat = party.chat
		chat.delete(core.ChatMessage(_data={'id':'chat1'}))
		self.assertFalse(chat._entries)
		self.assertEqual(chat.messages()[0].id, 'chat1')
		self.assertEqual(chat.messages()[0].timestamp, 1600000000)
		self.assertEqual(chat.messages()[0].user, 'person1')
		self.assertEqual(chat.messages()[0].text, 'Hello')
		chat.delete(core.ChatMessage(_data={'id':'chat1'}))
		self.assertEqual(chat.messages()[0].id, 'chat2')
		self.assertEqual(chat.messages()[0].timestamp, 1600001000)
		self.assertEqual(chat.messages()[0].user, 'person2')
		self.assertEqual(chat.messages()[0].text, 'Hello back')
	def should_post_messages(self):
		habitica = core.Habitica(_api=MockAPI(
			MockRequest('get', ['groups'], {'data': [{
					'name' : 'Party',
					'id' : 'group1',
					}]}),
			MockRequest('post', ['groups', 'group1', 'chat'], {'data': [{
					'id' : 'chat1',
					'user' : 'person1',
					'timestamp' : 1600000000,
					'text' : 'Hello',
					}]}),
			MockRequest('post', ['groups', 'group1', 'chat'], {'data': [{
					'id' : 'chat1',
					'user' : 'person1',
					'timestamp' : 1600000000,
					'text' : 'Hello',
					},{
					'id' : 'chat1.2',
					'user' : 'person1',
					'timestamp' : 1600000400,
					'text' : 'Hey?',
					},{
					'id' : 'chat2',
					'user' : 'person2',
					'timestamp' : 1600001000,
					'text' : 'Hello back',
					}]}),
			))

		party = habitica.groups(core.Group.PARTY)[0]
		chat = party.chat
		chat.post('Hello')
		self.assertEqual(chat.messages()[0].id, 'chat1')
		self.assertEqual(chat.messages()[0].timestamp, 1600000000)
		self.assertEqual(chat.messages()[0].user, 'person1')
		self.assertEqual(chat.messages()[0].text, 'Hello')
		chat.post('Hey?')
		self.assertEqual(chat.messages()[2].id, 'chat2')
		self.assertEqual(chat.messages()[2].timestamp, 1600001000)
		self.assertEqual(chat.messages()[2].user, 'person2')
		self.assertEqual(chat.messages()[2].text, 'Hello back')

class TestUser(unittest.TestCase):
	def _user_data(self, stats=None, **kwargs):
		result = {
				'stats' : {
					'class': 'rogue',
					'hp': 30.0,
					'maxHealth': 50.0,
					'lvl': 33,
					'exp': 1049.4,
					'toNextLevel': 51.6,
					'mp': 11.0,
					'maxMP': 55.0,
					'gp': 15.0,
					},
				'preferences' : {
					'timezoneOffset' : 180,
					},
				'items' : {
					'food' : [
						'Meat', 'Honey',
						],
					'currentPet' : 'Fox',
					'currentMount' : 'Wolf',
					},
				}
		if stats:
			result['stats'].update(stats)
		result.update(kwargs)
		return result
	def should_get_user_stats(self):
		habitica = core.Habitica(_api=MockAPI(
			MockRequest('get', ['user'], {'data': self._user_data()}),
			))
		user = habitica.user()
		self.assertEqual(user.stats.class_name, 'rogue')
		self.assertEqual(user.stats.hp, 30.0)
		self.assertEqual(user.stats.maxHealth, 50.0)
		self.assertEqual(user.stats.level, 33)
		self.assertEqual(user.stats.experience, 1049.4)
		self.assertEqual(user.stats.maxExperience, 1101.0)
		self.assertEqual(user.stats.mana, 11.0)
		self.assertEqual(user.stats.maxMana, 55.0)
		self.assertEqual(user.stats.gold, 15.0)
	def should_get_user_preferences(self):
		habitica = core.Habitica(_api=MockAPI(
			MockRequest('get', ['user'], {'data': self._user_data()}),
			))
		user = habitica.user()
		self.assertEqual(user.preferences.timezoneOffset, 180)
	def should_get_food_in_user_inventory(self):
		habitica = core.Habitica(_api=MockAPI(
			MockRequest('get', ['user'], {'data': self._user_data()}),
			))
		user = habitica.user()
		self.assertEqual(len(user.inventory.food), 2)
	def should_get_user_pet_and_mount(self):
		habitica = core.Habitica(_api=MockAPI(
			MockRequest('get', ['user'], {'data': self._user_data()}),
			))
		user = habitica.user()
		self.assertEqual(user.inventory.pet.text, 'Fox')
		self.assertEqual(user.inventory.mount.text, 'Wolf')
	def should_buy_health_potion(self):
		habitica = core.Habitica(_api=MockAPI(
			MockRequest('get', ['user'], {'data': self._user_data()}),
			MockRequest('post', ['user', 'buy-health-potion'], {
				'data': self._user_data(stats={'hp':45.0}),
				}),
			))
		user = habitica.user()
		potion = habitica.content.potion
		self.assertEqual(potion.text, 'Health Potion')
		self.assertEqual(potion.key, 'HealthPotion')
		self.assertEqual(potion.notes, 'Heals 15 hp')
		self.assertEqual(potion.type, 'potion')
		self.assertEqual(potion.cost, 25)
		self.assertEqual(potion.currency, 'gold')
		user.buy(potion)
		self.assertEqual(user.stats.hp, 45.0)

		with self.assertRaises(core.HealthOverflowError) as e:
			potion = core.HealthPotion()
			user.buy(potion)
		self.assertEqual(str(e.exception), 'HP is too high, part of health potion would be wasted.')

class TestQuest(unittest.TestCase):
	def should_show_progress_of_collection_quest(self):
		habitica = core.Habitica(_api=MockAPI(
			MockRequest('get', ['user'], {'data': {
				}}),
			MockRequest('get', ['groups', 'party'], {'data': {
				'quest' : {
					'active' : True,
					'key' : 'mycollectquest',
					'progress' : {
						'collect' : {
							'item1' : 7,
							'item2' : 3,
							}
						},
					},
				}}),
			))
		party = habitica.user().party()
		quest = party.quest
		self.assertTrue(quest.active)
		self.assertEqual(quest.key, 'mycollectquest')
		self.assertEqual(quest.title, 'Collect N items')
		self.assertEqual(quest.progress, 10)
		self.assertEqual(quest.max_progress, 100)
	def should_show_progress_of_boss_quest(self):
		habitica = core.Habitica(_api=MockAPI(
			MockRequest('get', ['user'], {'data': {
				}}),
			MockRequest('get', ['groups', 'party'], {'data': {
				'quest' : {
					'active' : True,
					'key' : 'mybossquest',
					'progress': {
						'hp' : 20,
						},
					},
				}}),
			))
		party = habitica.user().party()
		quest = party.quest
		self.assertTrue(quest.active)
		self.assertEqual(quest.key, 'mybossquest')
		self.assertEqual(quest.title, 'Slay Boss')
		self.assertEqual(quest.progress, 20)
		self.assertEqual(quest.max_progress, 200)

class TestRewards(unittest.TestCase):
	def should_get_user_rewards(self):
		habitica = core.Habitica(_api=MockAPI(
			MockRequest('get', ['user'], {'data': {
				}}),
			MockRequest('get', ['tasks', 'user'], {'data': [
				{'id':'reward1', 'text':'Eat'},
				{'id':'reward2', 'text':'Sleep'},
				],
				}),
			))
		user = habitica.user()
		rewards = user.rewards()
		self.assertEqual(rewards[0].id, 'reward1')
		self.assertEqual(rewards[0].text, 'Eat')
		self.assertEqual(rewards[1].id, 'reward2')
		self.assertEqual(rewards[1].text, 'Sleep')
	def should_buy_reward(self):
		habitica = core.Habitica(_api=MockAPI(
			MockRequest('get', ['user'], {'data': {
				}}),
			MockRequest('get', ['tasks', 'user'], {'data': [
				{'id':'reward1', 'text':'Eat'},
				{'id':'reward2', 'text':'Sleep'},
				],
				}),
			MockRequest('post', ['tasks', 'reward1', 'score', 'up'], {
				'data': {},
				}),
			))
		user = habitica.user()
		rewards = user.rewards()
		user.buy(rewards[0])

class TestHabits(unittest.TestCase):
	def should_get_list_of_user_habits(self):
		habitica = core.Habitica(_api=MockAPI(
			MockRequest('get', ['user'], {'data': {
				}}),
			MockRequest('get', ['tasks', 'user'], {'data': [
				{
					'id':'habit1',
					'text':'Keep calm',
					'notes':'And carry on',
					'value':5.1,
					'up':True,
					'down':False,
					},
				],
				}),
			))
		user = habitica.user()
		habits = user.habits()
		self.assertEqual(habits[0].id, 'habit1')
		self.assertEqual(habits[0].text, 'Keep calm')
		self.assertEqual(habits[0].notes, 'And carry on')
		self.assertEqual(habits[0].value, 5.1)
		self.assertEqual(habits[0].color, core.Task.LIGHT_BLUE)
		self.assertTrue(habits[0].can_score_up)
		self.assertFalse(habits[0].can_score_down)
	def should_separate_habits_by_color(self):
		habitica = core.Habitica(_api=MockAPI(
			MockRequest('get', ['user'], {'data': {
				}}),
			MockRequest('get', ['tasks', 'user'], {'data': [
				{ 'value':-50.1, },
				{ 'value':-15.4, },
				{ 'value':-5.6, },
				{ 'value':0.0, },
				{ 'value':1.1, },
				{ 'value':5.1, },
				{ 'value':15.1, },
				],
				}),
			))
		user = habitica.user()
		habits = user.habits()
		self.assertEqual(habits[0].color, core.Task.DARK_RED)
		self.assertEqual(habits[1].color, core.Task.RED)
		self.assertEqual(habits[2].color, core.Task.ORANGE)
		self.assertEqual(habits[3].color, core.Task.YELLOW)
		self.assertEqual(habits[4].color, core.Task.GREEN)
		self.assertEqual(habits[5].color, core.Task.LIGHT_BLUE)
		self.assertEqual(habits[6].color, core.Task.BRIGHT_BLUE)
	def should_score_habits_up(self):
		habitica = core.Habitica(_api=MockAPI(
			MockRequest('get', ['user'], {'data': {
				}}),
			MockRequest('get', ['tasks', 'user'], {'data': [
				{
					'id':'habit1',
					'text':'Keep calm',
					'value':5.1,
					'up':True,
					'down':False,
					},
				{
					'id':'habit2',
					'text':'Carry on',
					'value':5.1,
					'up':False,
					'down':False,
					},
				],
				}),
			MockRequest('post', ['tasks', 'habit1', 'score', 'up'], {'data': {
				'delta' : 1.1,
				}}),
			))
		user = habitica.user()
		habits = user.habits()
		habits[0].up()
		self.assertAlmostEqual(habits[0].value, 6.2)
		with self.assertRaises(core.CannotScoreUp) as e:
			habits[1].up()
		self.assertEqual(str(e.exception), "Habit 'Carry on' cannot be incremented")
	def should_score_habits_down(self):
		habitica = core.Habitica(_api=MockAPI(
			MockRequest('get', ['user'], {'data': {
				}}),
			MockRequest('get', ['tasks', 'user'], {'data': [
				{
					'id':'habit1',
					'text':'Keep calm',
					'value':5.1,
					'up':False,
					'down':True,
					},
				{
					'id':'habit2',
					'text':'Carry on',
					'value':5.1,
					'up':True,
					'down':False,
					},
				],
				}),
			MockRequest('post', ['tasks', 'habit1', 'score', 'down'], {'data': {
				'delta' : -1.1,
				}}),
			))
		user = habitica.user()
		habits = user.habits()
		habits[0].down()
		self.assertAlmostEqual(habits[0].value, 4.0)
		with self.assertRaises(core.CannotScoreDown) as e:
			habits[1].down()
		self.assertEqual(str(e.exception), "Habit 'Carry on' cannot be decremented")

class TestDailies(unittest.TestCase):
	def should_get_list_of_user_dailies(self):
		habitica = core.Habitica(_api=MockAPI(
			MockRequest('get', ['user'], {'data': {
				}}),
			MockRequest('get', ['tasks', 'user'], {'data': [
				{
					'id':'daily1',
					'text':'Rise',
					'notes':'And shine',
					'completed':False,
					'checklist': [
						{
							'id':'subdaily1',
							'text':'Rise',
							'completed':True,
							},
						{
							'id':'subdaily2',
							'text':'Shine',
							'completed':False,
							},
						],
					},
				],
				}),
			))
		user = habitica.user()
		dailies = user.dailies()
		self.assertEqual(dailies[0].id, 'daily1')
		self.assertEqual(dailies[0].text, 'Rise')
		self.assertEqual(dailies[0].notes, 'And shine')
		self.assertFalse(dailies[0].is_completed)

		checklist = dailies[0].checklist
		self.assertEqual(checklist[0].id, 'subdaily1')
		self.assertEqual(checklist[0].text, 'Rise')
		self.assertTrue(checklist[0].is_completed)
		self.assertEqual(checklist[0].parent.id, 'daily1')

		self.assertEqual(dailies[0][1].id, 'subdaily2')
		self.assertEqual(dailies[0][1].text, 'Shine')
		self.assertFalse(dailies[0][1].is_completed)
	def should_detect_due_dailies(self):
		habitica = core.Habitica(_api=MockAPI(
			MockRequest('get', ['user'], {'data': {
				}}),
			MockRequest('get', ['tasks', 'user'], {'data': [
				{
					'id':'daily1',
					'text':'Rise',
					'frequency':'daily',
					'startDate':'2016-06-20T21:00:00.000Z',
					'everyX':12,
					},
				{
					'id':'daily2',
					'text':'Survive Monday',
					'frequency':'weekly',
					'repeat':{
						"m":True,
						"t":False,
						"w":False,
						"th":False,
						"f":False,
						"s":False,
						"su":False,
						},
					},
				],
				}),
			))
		user = habitica.user()
		dailies = user.dailies()

		self.assertFalse(dailies[0].is_due(today=timeutils.parse_isodate('2016-11-09 16:51:15.930842'), timezoneOffset=-120))
		self.assertFalse(dailies[0].is_due(today=timeutils.parse_isodate('2016-11-10 16:51:15.930842'), timezoneOffset=-120))
		self.assertTrue(dailies[0].is_due(today=timeutils.parse_isodate('2016-11-11 16:51:15.930842'), timezoneOffset=-120))
		self.assertFalse(dailies[0].is_due(today=timeutils.parse_isodate('2016-11-12 16:51:15.930842'), timezoneOffset=-120))
		self.assertTrue(dailies[0].is_due(today=timeutils.parse_isodate('2016-11-23 16:51:15.930842'), timezoneOffset=-120))

		self.assertFalse(dailies[1].is_due(today=timeutils.parse_isodate('2016-11-09 16:51:15.930842'), timezoneOffset=-120))
		self.assertFalse(dailies[1].is_due(today=timeutils.parse_isodate('2016-11-10 16:51:15.930842'), timezoneOffset=-120))
		self.assertFalse(dailies[1].is_due(today=timeutils.parse_isodate('2016-11-11 16:51:15.930842'), timezoneOffset=-120))
		self.assertFalse(dailies[1].is_due(today=timeutils.parse_isodate('2016-11-12 16:51:15.930842'), timezoneOffset=-120))
		self.assertFalse(dailies[1].is_due(today=timeutils.parse_isodate('2016-11-13 16:51:15.930842'), timezoneOffset=-120))
		self.assertTrue(dailies[1].is_due(today=timeutils.parse_isodate('2016-11-14 16:51:15.930842'), timezoneOffset=-120))
		self.assertFalse(dailies[1].is_due(today=timeutils.parse_isodate('2016-11-15 16:51:15.930842'), timezoneOffset=-120))
		self.assertFalse(dailies[1].is_due(today=timeutils.parse_isodate('2016-11-16 16:51:15.930842'), timezoneOffset=-120))
	def should_complete_daily(self):
		habitica = core.Habitica(_api=MockAPI(
			MockRequest('get', ['user'], {'data': {
				}}),
			MockRequest('get', ['tasks', 'user'], {'data': [
				{
					'id':'daily1',
					'text':'Rise',
					'notes':'And shine',
					'completed':False,
					},
				],
				}),
			MockRequest('post', ['tasks', 'daily1', 'score', 'up'], {'data': {
				}}),
			MockRequest('post', ['tasks', 'daily1', 'score', 'down'], {'data': {
				}}),
			))
		user = habitica.user()
		dailies = user.dailies()
		self.assertFalse(dailies[0].is_completed)

		dailies[0].complete()
		self.assertTrue(dailies[0].is_completed)

		dailies[0].undo()
		self.assertFalse(dailies[0].is_completed)
	def should_complete_check_items(self):
		habitica = core.Habitica(_api=MockAPI(
			MockRequest('get', ['user'], {'data': {
				}}),
			MockRequest('get', ['tasks', 'user'], {'data': [
				{
					'id':'daily1',
					'text':'Rise',
					'notes':'And shine',
					'completed':False,
					'checklist': [
						{
							'id':'subdaily1',
							'text':'Rise',
							'completed':True,
							},
						{
							'id':'subdaily2',
							'text':'Shine',
							'completed':False,
							},
						],
					},
				],
				}),
			MockRequest('post', ['tasks', 'daily1', 'checklist', 'subdaily1', 'score'], {'data': {
				}}),
			MockRequest('post', ['tasks', 'daily1', 'checklist', 'subdaily2', 'score'], {'data': {
				}}),
			))
		user = habitica.user()
		dailies = user.dailies()
		self.assertFalse(dailies[0].is_completed)

		dailies[0][0].complete()
		self.assertTrue(dailies[0][0].is_completed)
		dailies[0][0].undo()
		self.assertFalse(dailies[0][0].is_completed)

		dailies[0][1].undo()
		self.assertFalse(dailies[0][1].is_completed)
		dailies[0][1].complete()
		self.assertTrue(dailies[0][1].is_completed)

class TestTodos(unittest.TestCase):
	def should_get_list_of_user_todos(self):
		habitica = core.Habitica(_api=MockAPI(
			MockRequest('get', ['user'], {'data': {
				}}),
			MockRequest('get', ['tasks', 'user'], {'data': [
				{
					'id':'todo1',
					'text':'Rise',
					'notes':'And shine',
					'completed':False,
					'checklist': [
						{
							'id':'subtodo1',
							'text':'Rise',
							'completed':True,
							},
						{
							'id':'subtodo2',
							'text':'Shine',
							'completed':False,
							},
						],
					},
				],
				}),
			))
		user = habitica.user()
		todos = user.todos()
		self.assertEqual(todos[0].id, 'todo1')
		self.assertEqual(todos[0].text, 'Rise')
		self.assertEqual(todos[0].notes, 'And shine')
		self.assertFalse(todos[0].is_completed)

		checklist = todos[0].checklist
		self.assertEqual(checklist[0].id, 'subtodo1')
		self.assertEqual(checklist[0].text, 'Rise')
		self.assertTrue(checklist[0].is_completed)
		self.assertEqual(checklist[0].parent.id, 'todo1')

		self.assertEqual(todos[0][1].id, 'subtodo2')
		self.assertEqual(todos[0][1].text, 'Shine')
		self.assertFalse(todos[0][1].is_completed)
	def should_complete_todo(self):
		habitica = core.Habitica(_api=MockAPI(
			MockRequest('get', ['user'], {'data': {
				}}),
			MockRequest('get', ['tasks', 'user'], {'data': [
				{
					'id':'todo1',
					'text':'Rise',
					'notes':'And shine',
					'completed':False,
					},
				],
				}),
			MockRequest('post', ['tasks', 'todo1', 'score', 'up'], {'data': {
				}}),
			MockRequest('post', ['tasks', 'todo1', 'score', 'down'], {'data': {
				}}),
			))
		user = habitica.user()
		todos = user.todos()
		self.assertFalse(todos[0].is_completed)

		todos[0].complete()
		self.assertTrue(todos[0].is_completed)

		todos[0].undo()
		self.assertFalse(todos[0].is_completed)
	def should_complete_check_items(self):
		habitica = core.Habitica(_api=MockAPI(
			MockRequest('get', ['user'], {'data': {
				}}),
			MockRequest('get', ['tasks', 'user'], {'data': [
				{
					'id':'todo1',
					'text':'Rise',
					'notes':'And shine',
					'completed':False,
					'checklist': [
						{
							'id':'subtodo1',
							'text':'Rise',
							'completed':True,
							},
						{
							'id':'subtodo2',
							'text':'Shine',
							'completed':False,
							},
						],
					},
				],
				}),
			MockRequest('post', ['tasks', 'todo1', 'checklist', 'subtodo1', 'score'], {'data': {
				}}),
			MockRequest('post', ['tasks', 'todo1', 'checklist', 'subtodo2', 'score'], {'data': {
				}}),
			))
		user = habitica.user()
		todos = user.todos()
		self.assertFalse(todos[0].is_completed)

		todos[0][0].complete()
		self.assertTrue(todos[0][0].is_completed)
		todos[0][0].undo()
		self.assertFalse(todos[0][0].is_completed)

		todos[0][1].undo()
		self.assertFalse(todos[0][1].is_completed)
		todos[0][1].complete()
		self.assertTrue(todos[0][1].is_completed)

class TestSpells(unittest.TestCase):
	def should_get_full_list_of_spells_for_user(self):
		habitica = core.Habitica(_api=MockAPI(
			MockRequest('get', ['user'], {'data': {
				'stats': {
					'class':'rogue',
					},
				}}),
			))
		user = habitica.user()
		spells = sorted(user.spells(), key=lambda s:s.name)
		self.assertEqual(spells[0].name, 'backStab')
		self.assertEqual(spells[1].name, 'pickPocket')
		self.assertEqual(spells[2].name, 'stealth')
		self.assertEqual(spells[3].name, 'toolsOfTrade')
	def should_get_specific_spell(self):
		habitica = core.Habitica(_api=MockAPI(
			MockRequest('get', ['user'], {'data': {
				'stats': {
					'class':'rogue',
					},
				}}),
			))
		user = habitica.user()
		spell = user.get_spell('smash')
		self.assertIsNone(spell)
		spell = user.get_spell('stealth')
		self.assertEqual(spell.name, 'stealth')
		self.assertEqual(spell.description, "Stealth")
	def should_cast_spell(self):
		habitica = core.Habitica(_api=MockAPI(
			MockRequest('get', ['user'], {'data': {
				'stats': {
					'class':'rogue',
					},
				}}),
			MockRequest('post', ['user', 'class', 'cast', 'stealth'], {'data': {
				}}),
			MockRequest('get', ['tasks', 'user'], {'data': [
				{
					'id':'todo1',
					'text':'Rise',
					'notes':'And shine',
					'completed':False,
					},
				],
				}),
			MockRequest('post', ['user', 'class', 'cast', 'backStab'], {'data': {
				}}),
			))
		user = habitica.user()
		spell = user.get_spell('stealth')
		user.cast(spell)
		target = user.todos()[0]
		spell = user.get_spell('backStab')
		user.cast(spell, target)
