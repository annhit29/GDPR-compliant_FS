"""""""""""""""""""""""""""""""""""""""""
# @author  sonus
# @date 02 - Apr - 2016
# @copyright sonus
# GitHub http://github.com/sonus21
"""""""""""""""""""""""""""""""""""""""""

from django import forms # type: ignore
from django.contrib.auth.forms import UserCreationForm # type: ignore
from django.contrib.auth import get_user_model # type: ignore
from twitt.models import Twit

User = get_user_model()

class SignUpForm(UserCreationForm):
	class Meta:
		model = User
		fields = ["username", 'first_name', 'last_name']

class TwitForm(forms.ModelForm):
	class Meta:
		model = Twit
		fields = ['content']
  





