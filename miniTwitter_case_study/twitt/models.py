from __future__ import unicode_literals
from typing import Any
from django.contrib.auth.models import User as BaseUser

from django.db import models
from ambient_toolbox.models import CommonInfo # type: ignore
from django.utils.timezone import now

from instrlib.django.orm import InstrumentORM

from .enforcer import logger

def info_user(user):
	try:
		return str(user)
	except:
		return ""

User = InstrumentORM(
	logger, 
	{"User.first_name", "User.last_name", "User.is_staff", "User.email", "User.save", "User.last_login"},
	info = info_user, events = {'read', 'write'}
)(BaseUser)

def info_follow(follow):
	try:
		return str(object.__getattribute__(follow, 'follower'))
	except:
		return ""

@InstrumentORM(logger, 
			   {"Follow.follower", "Follow.following", "Follow.date", "Follow"}, 
			   info = info_follow, events = {'read', 'write'})
class Follow(CommonInfo):
	"""
	Define Follow model which will hold list of follower and following
	and time when he/she started following
	"""
	follower  : models.ForeignKey    = models.ForeignKey(User, related_name='follower', db_index=True, on_delete=models.CASCADE)
	following : models.ForeignKey    = models.ForeignKey(User, related_name='following', db_index=True, on_delete=models.CASCADE)
	date      : models.DateTimeField = models.DateTimeField(default=now)

	class Meta:
		unique_together = ('follower', 'following')

def info_twit(twit):
	try:
		return str(object.__getattribute__(twit, 'author'))
	except:	
		return ""

@InstrumentORM(logger, 
			   {"Twit.content", "Twit.posted_on", "Twit.updated_on", "Twit.author", "Twit.save"},
			   info = info_twit, events = {'read', 'write'})
class Twit(CommonInfo):
	"""
	Twit model which holds twit data
	"""
	content    : models.CharField     = models.CharField(max_length=140)
	posted_on  : models.DateTimeField = models.DateTimeField(default=now)
	updated_on : models.DateTimeField = models.DateTimeField(default=now, db_index=True)
	author     : models.ForeignKey    = models.ForeignKey(User, db_index=True, on_delete=models.CASCADE)

	def save(self, *args, **kwargs):
		if self.posted_on is None:
			self.posted_on = now()
			self.updated_on = now()
		else:
			self.updated_on = now()
		super(Twit, self).save(*args, **kwargs)
