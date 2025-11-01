"""""""""""""""""""""""""""""""""""""""""
# @author  sonus
# @date 02 - Apr - 2016
# @copyright sonus
# GitHub http://github.com/sonus21
"""""""""""""""""""""""""""""""""""""""""

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from twitt.models import Twit

# from twitt.models import User


class SignUpForm(UserCreationForm):
	class Meta:
		model = User
		fields = ["username",'first_name','last_name']

class TwitForm(forms.ModelForm):
	class Meta:
		model = Twit
		fields = ['content']
  





