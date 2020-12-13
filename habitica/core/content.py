""" Habitica's content: database of all availables items and definitions.
"""
import datetime
from collections import namedtuple
from . import base

HabiticaEvent = namedtuple('HabiticaEvent', 'start end')

class Content:
	""" Cache for all Habitica content. """
	def __init__(self, _api=None):
		self.api = _api
		self._data = self.api.cached('content').get('content').data
	@property
	def potion(self):
		return HealthPotion(_api=self.api, _data=self._data['potion'])
	@property
	def armoire(self):
		return Armoire(_api=self.api, _data=self._data['armoire'])
	@property
	def classes(self):
		return self._data['classes']
	@property
	def gearTypes(self):
		return self._data['gearTypes']
	def questEggs(self):
		return [Egg(_api=self.api, _data=entry) for entry in self._data['questEggs'].values()]
	def eggs(self):
		return [Egg(_api=self.api, _data=entry) for entry in self._data['eggs'].values()]
	def dropEggs(self):
		return [Egg(_api=self.api, _data=entry) for entry in self._data['dropEggs'].values()]
	def wackyHatchingPotions(self):
		return [HatchingPotion(_api=self.api, _data=entry) for entry in self._data['wackyHatchingPotions'].values()]
	def hatchingPotions(self):
		return [HatchingPotion(_api=self.api, _data=entry) for entry in self._data['hatchingPotions'].values()]
	def dropHatchingPotions(self):
		return [HatchingPotion(_api=self.api, _data=entry) for entry in self._data['dropHatchingPotions'].values()]
	def premiumHatchingPotions(self):
		return [HatchingPotion(_api=self.api, _data=entry) for entry in self._data['premiumHatchingPotions'].values()]
	def petInfo(self, key=None):
		if key:
			return Pet(_api=self.api, _data=self._data['petInfo'][key])
		return [Pet(_api=self.api, _data=entry) for entry in self._data['petInfo'].values()]
	def questPets(self):
		return [Pet(_api=self.api, _data=self._data['petInfo'][key]) for key, value in self._data['questPets'].items() if value]
	def premiumPets(self):
		return [Pet(_api=self.api, _data=self._data['petInfo'][key]) for key, value in self._data['premiumPets'].items() if value]
	def specialPets(self):
		return [Pet(_api=self.api, _data=self._data['petInfo'][key], _special=value) for key, value in self._data['specialPets'].items() if value]
	def mountInfo(self, key=None):
		if key:
			return Mount(_api=self.api, _data=self._data['mountInfo'][key])
		return [Mount(_api=self.api, _data=entry) for entry in self._data['mountInfo'].values()]
	def mounts(self):
		return [Mount(_api=self.api, _data=self._data['mountInfo'][key]) for key, value in self._data['mounts'].items() if value]
	def questMounts(self):
		return [Mount(_api=self.api, _data=self._data['mountInfo'][key]) for key, value in self._data['questMounts'].items() if value]
	def premiumMounts(self):
		return [Mount(_api=self.api, _data=self._data['mountInfo'][key]) for key, value in self._data['premiumMounts'].items() if value]
	def specialMounts(self):
		return [Mount(_api=self.api, _data=self._data['mountInfo'][key], _special=value) for key, value in self._data['specialMounts'].items() if value]
	def get_background(self, name):
		return Background(_data=self._data['backgroundFlats'][name], _api=self.api)
	def get_background_set(self, year, month=None):
		""" Returns background set for given year and month.
		If month is None, returns all sets for this year.
		If year is None (explicitly), returns time travel backgrounds.
		"""
		if year is None: # TODO time travel - needs some constant name
			return [Background(_api=self.api, _data=entry) for entry in self._data['backgrounds']['timeTravelBackgrounds']]
		months = ['{0:02}'.format(month)] if month else ['{0:02}'.format(number) for number in range(1, 13)]
		patterns = ['backgrounds{month}{year}'.format(year=year, month=month) for month in months]
		result = []
		for key in self._data['backgrounds']:
			if key in patterns:
				result += [Background(_api=self.api, _data=entry) for entry in self._data['backgrounds'][key]]
		return result
	def __getitem__(self, key):
		try:
			return object.__getitem__(self, key)
		except AttributeError:
			return self._data[key]

class Armoire(base.ApiObject):
	@property
	def text(self):
		return self._data['text']
	@property
	def key(self):
		return self._data['key']
	@property
	def type(self):
		return self._data['type']
	@property
	def cost(self):
		return self._data['value']
	@property
	def currency(self):
		return 'gold'

class Egg(base.ApiObject):
	@property
	def key(self):
		return self._data['key']
	@property
	def text(self):
		return self._data['text']
	@property
	def mountText(self):
		return self._data['mountText']
	@property
	def notes(self):
		return self._data['notes']
	@property
	def adjective(self):
		return self._data['adjective']
	@property
	def price(self):
		return self._data['value']
	@property
	def currency(self):
		return 'gems'

class HatchingPotion(base.ApiObject):
	@property
	def key(self):
		return self._data['key']
	@property
	def text(self):
		return self._data['text']
	@property
	def notes(self):
		return self._data['notes']
	@property
	def _addlNotes(self):
		return self._data.get('_addlNotes', '')
	@property
	def price(self):
		return self._data['value']
	@property
	def currency(self):
		return 'gems'
	@property
	def premium(self):
		return self._data.get('premium', False)
	@property
	def limited(self):
		return self._data.get('limited', False)
	@property
	def wacky(self):
		return self._data.get('wacky', False)
	@property
	def event(self):
		if 'event' not in self._data:
			return None
		start = datetime.datetime.strptime(self._data['event']['start'], '%Y-%m-%d').date()
		end = datetime.datetime.strptime(self._data['event']['end'], '%Y-%m-%d').date()
		return HabiticaEvent(start, end)

class Food(base.ApiObject): # pragma: no cover -- FIXME no methods to retrieve yet.
	@property
	def key(self):
		return self._data['key']
	@property
	def text(self):
		return self._data['text']
	@property
	def textThe(self):
		return self._data['textThe']
	@property
	def textA(self):
		return self._data['textA']
	@property
	def target(self):
		return self._data['target']
	@property
	def notes(self):
		return self._data['notes']
	@property
	def canDrop(self):
		return self._data['canDrop']
	@property
	def price(self):
		return self._data['value']
	@property
	def currency(self):
		return 'gems'

class Background(base.ApiObject):
	def __init__(self, _data=None, _api=None):
		self.api = _api
		self._data = _data
	@property
	def text(self):
		return self._data['text']
	@property
	def notes(self):
		return self._data['notes']
	@property
	def key(self):
		return self._data['key']
	@property
	def price(self):
		return self._data['price']
	@property
	def currency(self):
		return self._data['currency'] if 'currency' in self._data else 'gems'
	@property
	def set_name(self):
		return self._data['set']

class HealthOverflowError(Exception):
	def __init__(self, hp, maxHealth):
		self.hp, self.maxHealth = hp, maxHealth
	def __str__(self):
		return 'HP is too high, part of health potion would be wasted.'

class HealthPotion(base.ApiObject):
	""" Health potion (+15 hp). """
	VALUE = 15.0
	def __init__(self, overflow_check=True, **kwargs):
		""" If overflow_check is True and there is less than 15 hp damage,
		so buying potion will result in hp bar overflow and wasting of potion,
		raises HealthOverflowError.
		"""
		super().__init__(**kwargs)
		self.overflow_check = overflow_check
	@property
	def text(self):
		return self._data['text']
	@property
	def notes(self):
		return self._data['notes']
	@property
	def key(self):
		return self._data['key']
	@property
	def type(self):
		return self._data['type']
	@property
	def cost(self):
		return self._data['value']
	@property
	def currency(self):
		return 'gold'
	def _buy(self, user):
		if self.api is None:
			self.api = user.api
		if self.overflow_check and user.stats.hp + self.VALUE > user.stats.maxHealth:
			raise HealthOverflowError(user.stats.hp, user.stats.maxHealth)
		user._data = self.api.post('user', 'buy-health-potion').data

class Pet(base.ApiObject):
	def __init__(self, _special=None, **kwargs):
		super().__init__(**kwargs)
		self._special = _special
	def __str__(self):
		return self.text
	@property
	def text(self):
		return self._data['text']
	@property
	def key(self):
		return self._data['key']
	@property
	def type(self):
		return self._data['type']
	@property
	def egg(self):
		return self._data.get('egg', None)
	@property
	def potion(self):
		return self._data.get('potion', None)
	@property
	def canFind(self):
		return self._data.get('canFind', None)
	@property
	def special(self):
		return self._special

class Mount(base.ApiObject):
	def __init__(self, _special=None, **kwargs):
		super().__init__(**kwargs)
		self._special = _special
	def __str__(self):
		return self.text
	@property
	def text(self):
		return self._data['text']
	@property
	def key(self):
		return self._data['key']
	@property
	def type(self):
		return self._data['type']
	@property
	def egg(self):
		return self._data.get('egg', None)
	@property
	def potion(self):
		return self._data.get('potion', None)
	@property
	def canFind(self):
		return self._data.get('canFind', None)
	@property
	def special(self):
		return self._special
