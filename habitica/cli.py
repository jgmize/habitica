#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Phil Adams http://philadams.net

habitica: commandline interface for http://habitica.com
http://github.com/philadams/habitica
"""

import logging
logger = logging.getLogger('habitica')
import os.path
import datetime
import sys
import re
import argparse
import functools, itertools
import operator
from webbrowser import open_new_tab
from collections import namedtuple
from pathlib import Path

import termcolor

from . import api, core
from .core import Habitica, Group
from . import timeutils, config
from . import extra

logging.PRINT = (logging.INFO + logging.WARNING)//2
logging.addLevelName(logging.PRINT, 'PRINT')
def _log_print(self, message, *args, **kwargs): # pragma: no cover
	if self.isEnabledFor(logging.PRINT):
		self._log(logging.PRINT, message, args, **kwargs)
logger.print = _log_print.__get__(logger)

if sys.stdout and not sys.stdout.isatty(): # pragma: no cover
	os.environ['ANSI_COLORS_DISABLED'] = '1'

class ComplexFormatter: # pragma: no cover
	def __init__(self):
		self._formatters = {
				logging.DEBUG: logging.Formatter(
					'%(asctime)s:%(name)s:%(levelname)s:%(module)s:%(lineno)d:%(funcName)s: %(message)s',
					),
				logging.INFO: logging.Formatter(
					termcolor.colored('%(message)s', 'green'),
					),
				logging.PRINT: logging.Formatter(
					'%(message)s',
					),
				logging.WARNING: logging.Formatter(
					termcolor.colored('%(message)s', 'yellow'),
					),
				logging.ERROR: logging.Formatter(
					termcolor.colored('%(message)s', 'red'),
					),
				logging.CRITICAL: logging.Formatter(
					termcolor.colored('!!! %(message)s', 'red', attrs=['bold']),
					),
				}
		self._default = logging.Formatter('%(message)s')
	def format(self, record):
		formatter = self._formatters.get(record.levelno, self._default)
		return formatter.format(record)

VERSION = 'habitica version 0.1.0'
# https://trello.com/c/4C8w1z5h/17-task-difficulty-settings-v2-priority-multiplier
PRIORITY = {'easy': 1,
			'medium': 1.5,
			'hard': 2}

def task_id_key(task_id):
	SUBTASK_ORDER, TASK_ORDER = 0, 1
	if isinstance(task_id, int):
		return (task_id, TASK_ORDER, 0)
	else:
		task_id, subtask_id = task_id
		return (task_id, SUBTASK_ORDER, subtask_id)

def parse_task_number_arg(raw_arg):
	task_ids = []
	for bit in raw_arg.split(','):
		if '-' in bit:
			start, stop = [int(e) - 1 for e in bit.split('-')]
			task_ids.extend(range(start, stop + 1))
		elif '.' in bit:
			task_ids.append(tuple([int(e) - 1 for e in bit.split('.')]))
		else:
			task_ids.append(int(bit) - 1)
	return task_ids

def enumerate_with_subitems(tasks):
	""" Yields pairs: <index>, <task>
	If task has checklist, yields subitems before the parent task.
	For subitems indexes are tuples: (<parent task index>, <checklist item index>).
	"""
	for index, task in enumerate(tasks):
		if isinstance(task, core.Checklist):
			for subindex, subitem in enumerate(task.checklist):
				yield (index, subindex), subitem
		yield index, task

def filter_tasks(tasks, patterns):
	""" Filters task list by user-input patterns (like command line args).
	Patterns can be of two kinds:
	- Indexes in the task list.
	  Indexes can be separated by commas or grouped in ranges: 1,2-5
	  Sub-items (tasks' checklist items) are addressed via dot: 1.1 1.2 etc.
	  Indexing starts with 1.
	- Full or partial task caption.
	  If two or more tasks match same pattern, RuntimeError is raised.
	  If pattern is not found at all, RuntimeError is raised.
	Yields tasks or checklist items.
	Checklist items are yielded before their parent task: 1.1, 1.2, 1
	"""
	indexes, text_patterns = [], set()
	TASK_NUMBERS = re.compile(r'^(\d+(-\d+)?,?)+')
	for raw_arg in patterns:
		if TASK_NUMBERS.match(raw_arg):
			indexes.extend(parse_task_number_arg(raw_arg))
		else:
			text_patterns.add(raw_arg)

	processed_patterns = set()
	for index, task in enumerate_with_subitems(tasks):
		if index in indexes:
			yield task
			continue
		matched = {pattern for pattern in text_patterns if pattern in task.text}
		if not matched:
			continue
		if len(matched) > 1:
			raise RuntimeError("Several patterns match single task '{0}':\n" + '\n'.join(matched))
		if matched & processed_patterns:
			raise RuntimeError("Pattern {0} matches multiple tasks!".format(', '.join(map(repr, matched & processed_patterns))))
		processed_patterns |= matched
		yield task
	unprocessed = text_patterns - processed_patterns
	if unprocessed:
		raise RuntimeError("couldn't find task that includes {0}".format(', '.join(map(repr, unprocessed))))

def print_task_list(tasks, hide_completed=False, timezoneOffset=0, with_notes=False, time_now=None, printer=None):
	printer = printer or logger.print
	time_now = time_now or datetime.datetime.now()
	for i, task in enumerate(tasks):
		if isinstance(task, core.Daily) and not task.is_due(time_now, timezoneOffset=timezoneOffset):
			continue
		if isinstance(task, core.Checkable):
			if task.is_completed and hide_completed:
				continue
			printer('- [%s] %s %s' % ('X' if task.is_completed else ' ', i + 1, task.text))
		else:
			printer('%s %s' % (i + 1, task.text))
		if with_notes and task.notes:
			printer('\n'.join('      {0}'.format(line) for line in task.notes.splitlines()))
		if isinstance(task, core.Checklist):
			for j, item in enumerate(task.checklist):
				completed = 'X' if item.is_completed else ' '
				printer('  - [%s] %s.%s %s' % (completed, i + 1, j + 1, item.text))

TASK_SCORES = {
		core.Task.DARK_RED	  : '<<<   ',
		core.Task.RED		  : ' <<   ',
		core.Task.ORANGE	  : '  <   ',
		core.Task.YELLOW	  : '      ',
		core.Task.GREEN		  : '   >  ',
		core.Task.LIGHT_BLUE  : '   >> ',
		core.Task.BRIGHT_BLUE : '   >>>',
		}

import click, click_default_group

class PrintEventHandler(core.base.EventHandler): # pragma: no cover
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._enabled = True
	def printing_enabled(self, value):
		self._enabled = bool(value)
	def add(self, event):
		if self._enabled:
			print(str(event), file=sys.stderr)

@click.group()
@click.version_option(version=VERSION)
@click.option('-q', '--quiet', is_flag=True, help='Hide any normal output, show only warnings and errors.')
@click.option('-v', '--verbose', is_flag=True, help='Show some logging information')
@click.option('-d', '--debug', is_flag=True, help='Show all logging information')
@click.option('--notifications/--no-notifications', default=True, help='Display notifications from Habitica (prints to stderr). By default is enabled.')
@click.pass_context
def cli(ctx, quiet=False, verbose=False, debug=False, notifications=False): # pragma: no cover
	""" Habitica command-line interface. """
	# Click's context object is authenticated Habitica endpoint.
	ctx.obj = Habitica(auth=config.load_auth(), event_handler=PrintEventHandler())
	if not notifications or quiet:
		ctx.obj.events.printing_enabled(False)

	if not logger.handlers:
		handler = logging.StreamHandler(sys.stdout)
		handler.setFormatter(ComplexFormatter())
		logger.addHandler(handler)

	# set up logging
	logger.setLevel(logging.PRINT)
	if quiet:
		logger.setLevel(logging.WARNING)
	if verbose:
		logger.setLevel(logging.INFO)
	if debug:
		logger.setLevel(logging.DEBUG)

@cli.command()
@click.pass_obj
def status(habitica): # pragma: no cover
	""" Show HP, XP, GP, and more """
	# gather status info
	user = habitica.user()
	stats = user.stats

	quest = user.party().quest
	if quest and quest.active:
		if quest.boss:
			progress = quest.boss.hp
		else:
			progress = quest.collect.current
		quest_info = '{0}/{1} "{2}"'.format(int(progress),
				int(progress.max_value),
				quest.title)
	else:
		quest_info = '-'

	# prepare and print status strings
	title = 'Level %d %s' % (stats.level, stats.class_name.capitalize())
	logger.print('-' * len(title))
	logger.print(title)
	logger.print('-' * len(title))
	rows = [
			('Health', '%d/%d' % (stats.hp, stats.maxHealth)),
			('XP', '%d/%d' % (int(stats.experience), stats.maxExperience)),
			('Mana', '%d/%d' % (int(stats.mana), stats.maxMana)),
			('Gold', '%d' % (int(stats.gold),)),
			('Pet', '%s (%d food items)' % (user.inventory.pet or '-', sum(_.amount for _ in user.inventory.food))),
			('Mount', user.inventory.mount or '-'),
			('Quest', quest_info),
			]
	len_ljust = max(map(len, map(operator.itemgetter(0), rows))) + 2
	for row_title, value in rows:
		logger.print('%s: %s' % (row_title.rjust(len_ljust, ' '), value))

@cli.command()
@click.pass_obj
def server(habitica): # pragma: no cover
	""" Show status of Habitica service """
	if habitica.server_is_up():
		logger.info('Habitica server is up')
	else:
		logger.error('Habitica server down... or your computer cannot connect')
		sys.exit(1)

@cli.command()
@click.pass_obj
def home(habitica): # pragma: no cover
	""" Open tasks page in default browser """
	home_url = habitica.home_url()
	logger.info('Opening %s' % home_url)
	open_new_tab(home_url)

@cli.command()
@click.argument('item', required=False)
@click.option('--full', is_flag=True, help='Print tasks details along with the title.')
@click.pass_obj
def reward(habitica, item=None, full=False): # pragma: no cover
	""" Buys or lists available items in reward column

	If ITEM is not specified, lists all available items.
	"""
	user = habitica.user()
	rewards = user.rewards()
	if item is None:
		print_task_list(rewards)
	else:
		for reward in filter_tasks(rewards, [item]):
			user.buy(reward)
			logger.print('bought reward \'%s\'' % reward.text)

@cli.group(cls=click_default_group.DefaultGroup, default='list', default_if_no_args=True)
@click.pass_obj
def habits(habitica): # pragma: no cover
	""" Manage habit tasks """

def print_habits(habits, full=False): # pragma: no cover
	with_notes = full
	for i, task in enumerate(habits):
		score = TASK_SCORES[task.color]
		updown = {0:' ', 1:'-', 2:'+', 3:'±'}[int(task.can_score_up)*2 + int(task.can_score_down)] # [up][down] as binary number
		logger.print('[{3}|{0}] {1} {2}'.format(score, i + 1, task.text, updown))
		if with_notes:
			logger.print('\n'.join('	   {0}'.format(line) for line in task.notes.splitlines()))

@habits.command('list')
@click.option('--full', is_flag=True, help='Print tasks details along with the title.')
@click.pass_obj
def habits_list(habitica, full=False): # pragma: no cover
	""" List habit tasks """
	habits = habitica.user.habits()
	print_habits(habits, full=full)

@habits.command('up')
@click.argument('tasks', nargs=-1, required=True)
@click.option('--full', is_flag=True, help='Print tasks details along with the title.')
@click.pass_obj
def habits_up(habitica, tasks, full=False): # pragma: no cover
	""" Up (+) habit

	You can pass one or more <task-id> parameters, using either comma-separated lists or ranges or both. For example, `todos done 1,3,6-9,11`.
	"""
	habits = habitica.user.habits()
	for habit in filter_tasks(habits, tasks):
		try:
			habit.up()
			logger.print('incremented task \'%s\'' % habit.text)
		except CannotScoreUp as e:
			logger.error(e)
			continue
	print_habits(habits, full=full)

@habits.command('down')
@click.argument('tasks', nargs=-1, required=True)
@click.option('--full', is_flag=True, help='Print tasks details along with the title.')
@click.pass_obj
def habits_down(habitica, tasks, full=False): # pragma: no cover
	""" Down (-) habit

	You can pass one or more <task-id> parameters, using either comma-separated lists or ranges or both. For example, `todos done 1,3,6-9,11`.
	"""
	habits = habitica.user.habits()
	for habit in filter_tasks(habits, tasks):
		try:
			habit.down()
			logger.print('decremented task \'%s\'' % habit.text)
		except CannotScoreDown as e:
			logger.error(e)
			continue
	print_habits(habits, full=full)

@cli.group(cls=click_default_group.DefaultGroup, default='list', default_if_no_args=True)
@click.pass_obj
def dailies(habitica): # pragma: no cover
	""" Manage daily tasks """

@dailies.command('list')
@click.option('--full', is_flag=True, help='Print tasks details along with the title.')
@click.option('--list-all', is_flag=True, help='List all dailies. By default only not done dailies will be displayed')
@click.pass_obj
def dailies_list(habitica, full=False, list_all=False): # pragma: no cover
	""" List daily tasks """
	user = habitica.user()
	timezoneOffset = user.preferences.timezoneOffset
	dailies = user.dailies()
	print_task_list(dailies, hide_completed=not list_all, timezoneOffset=timezoneOffset, with_notes=full)

@dailies.command('done')
@click.argument('tasks', nargs=-1, required=True)
@click.option('--full', is_flag=True, help='Print tasks details along with the title.')
@click.option('--list-all', is_flag=True, help='List all dailies. By default only not done dailies will be displayed')
@click.pass_obj
def dailies_done(habitica, tasks, full=False, list_all=False): # pragma: no cover
	""" Mark daily complete

	You can pass one or more <task-id> parameters, using either comma-separated lists or ranges or both. For example, `todos done 1,3,6-9,11`.
	"""
	user = habitica.user()
	timezoneOffset = user.preferences.timezoneOffset
	dailies = user.dailies()
	for task in filter_tasks(dailies, tasks):
		title = task.text
		if hasattr(task, 'parent'):
			title = task.parent.text + ' : ' + title
		task.complete()
		logger.print('marked daily \'%s\' completed' % title)
	print_task_list(dailies, hide_completed=not list_all, timezoneOffset=timezoneOffset, with_notes=full)

@dailies.command('undo')
@click.argument('tasks', nargs=-1, required=True)
@click.option('--full', is_flag=True, help='Print tasks details along with the title.')
@click.option('--list-all', is_flag=True, help='List all dailies. By default only not done dailies will be displayed')
@click.pass_obj
def dailies_undo(habitica, tasks, full=False, list_all=False): # pragma: no cover
	""" Mark daily incomplete

	You can pass one or more <task-id> parameters, using either comma-separated lists or ranges or both. For example, `todos done 1,3,6-9,11`.
	"""
	user = habitica.user()
	timezoneOffset = user.preferences.timezoneOffset
	dailies = user.dailies()
	for task in filter_tasks(dailies, tasks):
		title = task.text
		if hasattr(task, 'parent'):
			title = task.parent.text + ' : ' + title
		task.undo()
		logger.print('marked daily \'%s\' incomplete' % title)
	print_task_list(dailies, hide_completed=not list_all, timezoneOffset=timezoneOffset, with_notes=full)

@cli.group(cls=click_default_group.DefaultGroup, default='list', default_if_no_args=True)
@click.pass_obj
def todos(habitica): # pragma: no cover
	""" Manage todo tasks """

@todos.command('list')
@click.option('--full', is_flag=True, help='Print tasks details along with the title.')
@click.pass_obj
def todos_list(habitica, full=False): # pragma: no cover
	""" List todo tasks """
	todos = [e for e in habitica.user.todos() if not e.is_completed]
	with_notes = full
	print_task_list(todos, with_notes=full, hide_completed=True)

@todos.command('done')
@click.argument('tasks', nargs=-1, required=True)
@click.option('--full', is_flag=True, help='Print tasks details along with the title.')
@click.pass_obj
def todos_done(habitica, tasks, full=False): # pragma: no cover
	""" Mark one or more todo completed

	You can pass one or more <task-id> parameters, using either comma-separated lists or ranges or both. For example, `todos done 1,3,6-9,11`.
	"""
	todos = [e for e in habitica.user.todos() if not e.is_completed]
	for task in filter_tasks(todos, tasks):
		title = task.text
		if hasattr(task, 'parent'):
			title = task.parent.text + ' : ' + title
		task.complete()
		logger.print('marked todo \'%s\' completed' % title)
	with_notes = full
	print_task_list(todos, with_notes=full, hide_completed=True)

@todos.command('add')
#@click.option('--difficulty', type=click.Choice(['easy', 'medium', 'hard']), default='easy')
@click.pass_obj
def todos_add(habitica): # difficuly=None): # pragma: no cover -- FIXME not tested and probably not working, should replace with proper creation action.
	""" Add todo with description
	"""
	todos = [e for e in habitica.user.todos() if not e.is_completed]
	ttext = ' '.join(task)
	habitica.hbt.tasks(type='todos',
				   text=ttext,
				   priority=PRIORITY[difficulty],
				   _method='post')
	todos.insert(0, {'completed': False, 'text': ttext})
	logger.print('added new todo \'%s\'' % ttext)
	with_notes = full
	print_task_list(todos, with_notes=full, hide_completed=True)

@cli.command()
@click.pass_obj
def health(habitica): # pragma: no cover
	""" Buy health potion """
	user = habitica.user()
	try:
		user.buy(habitica.content.potion)
		logger.print('Bought Health Potion, HP: {0:.1f}/{1}'.format(user.stats.hp, user.stats.maxHealth))
	except core.HealthOverflowError as e:
		logger.error(e)
		logger.error('HP: {0:.1f}/{1}, need at most {2:.1f}'.format(user.stats.hp, user.stats.maxHealth, user.stats.maxHealth - core.HealthPotion.VALUE))

@cli.command()
@click.argument('cast', required=False)
@click.option('--habit', 'habits', multiple=True, help='Specifies habits as targets to cast the spell on (if applied)')
@click.option('--todo', 'todos', multiple=True, help='Specifies todos as targets to cast the spell on (if applied)')
@click.pass_obj
def spells(habitica, cast=None, habits=None, todos=None): # pragma: no cover
	""" Casts or list available spells

	If spell to CAST is not specified, lists available spells.
	"""
	user = habitica.user()
	user_class = user.stats.class_name
	if not cast:
		for spell in user.spells():
			logger.print('{0} - {1}: {2}'.format(spell.key, spell.text, spell.description))
		return

	spell_key = cast
	try:
		spell = user.get_spell(spell_key)
	except KeyError:
		logger.error('{1} cannot cast spell {0}'.format(user_class.title(), spell_key))
		return False

	targets = []
	if habits:
		targets.extend(filter_tasks(user.habits(), habits))
	elif todos:
		targets.extend(filter_tasks(user.todos(), todos))
	if targets:
		for target in targets:
			if user.cast(spell, target):
				logger.print('Casted spell "{0}"'.format(spell.text))
			else:
				sys.exit(1)
	else:
		user.cast(spell)
		logger.print('Casted spell "{0}"'.format(spell.text))

@cli.command()
@click.argument('count', required=False, type=int, default=0)
@click.option('--seen', is_flag=True, help='Mark all messages as read.')
@click.option('--json', 'as_json', is_flag=True, help='Print all messages in JSON format.')
@click.option('--rss', 'as_rss', is_flag=True, help='Print all messages in RSS format.')
@click.option('-o', '--output', help="File to store fetched messages. By default or if specified as '-', prints to stdout.")
@click.pass_obj
def messages(habitica, count=None, seen=False, as_json=False, as_rss=False, output=None): # pragma: no cover
	""" Lists last messages for all guilds user is in.

	If max COUNT of messages is not specified or specified as 0, displays all messages.

	If output is stdout, disables displaying notifications.
	"""
	if output == '-':
		output = None
	if not output:
		habitica.events.printing_enabled(False)
	mark_as_seen = seen
	if as_json and as_rss:
		logger.error('Only one type of export could be specified: --rss, --json')
		sys.exit(1)
	max_count = 0 # By default no restriction - print all messages.
	if count:
		max_count = int(count)

	groups = habitica.groups(Group.GUILDS, Group.PARTY)
	if not groups:
		logger.error('Failed to fetch list of user guilds')
		return
	if as_rss:
		exporter = extra.RSSMessageFeed()
	elif as_json:
		exporter = extra.JsonMessageFeed()
	else:
		exporter = extra.TextMessageFeed()
	for group in groups:
		chat_messages = group.chat()
		if not chat_messages:
			logger.error('Failed to fetch messages of chat {0}'.format(group.name))
			continue
		if max_count:
			chat_messages = chat_messages[:max_count]
		for entry in chat_messages:
			message = {
					'id' : entry.id,
					'username': entry.user,
					'timestamp': int(entry.timestamp / 1000),
					'text': entry.text,
					}
			exporter.add_message(group._data, message) # FIXME: Use Group and ChatMessage objects instead.
		if mark_as_seen:
			group.mark_chat_as_read()
	exporter.done()
	if output:
		Path(output).write_text(exporter.getvalue())
	else:
		sys.stdout.write(exporter.getvalue())

@cli.command('news')
@click.option('--seen', is_flag=True, help='Mark news post as read.')
@click.pass_obj
def show_news(habitica, seen=False): # pragma: no cover
	news = habitica.news()
	sys.stdout.write(news.html_text)
	if seen:
		news.mark_as_read()

@cli.command('tavern')
@click.option('--in', 'go_in', is_flag=True, help='Enter tavern to rest.')
@click.option('--out', 'go_out', is_flag=True, help='Exit tavern.')
@click.option('--toggle', is_flag=True, help='Toggle current state of resting in/out.')
@click.pass_obj
def tavern(habitica, go_in=False, go_out=False, toggle=False): # pragma: no cover
	""" Controls tavern state (in/out).
	Without options just prints current state.
	"""
	if sum(map(int, (go_in, go_out, toggle))) > 1:
		logger.error('Only one flag can be specified')
		return False
	user = habitica.user()
	if toggle:
		if user.preferences.sleep:
			go_out = True
		else:
			go_in = True
	if go_in:
		user.sleep()
	elif go_out:
		user.wake_up()
	if user.preferences.sleep:
		logger.print('Resting in inn.')
	else:
		logger.print('Out of tavern.')

if __name__ == '__main__': # pragma: no cover
	cli()
