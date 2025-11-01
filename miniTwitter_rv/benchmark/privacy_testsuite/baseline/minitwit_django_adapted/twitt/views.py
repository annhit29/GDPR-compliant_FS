from django.contrib.auth import logout
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, get_object_or_404
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.utils.timezone import now
from django.views import View
from django.views.generic import TemplateView, CreateView, FormView, UpdateView
import redis

from .models import Twit, Follow, User
from twitt.forms import SignUpForm, TwitForm

class LoginRequiredMixin(object):
	"""It ensures that user is authenticated

	"""

	@method_decorator(login_required)
	def dispatch(self, request, *args, **kwargs):
		return super(LoginRequiredMixin, self).dispatch(request, *args, **kwargs)


class HomeView(LoginRequiredMixin, TemplateView):
	"""Home page login is required

	"""
	template_name = 'index.html'

	def generate_advertisement(self):
		keyword = "GDPR"
		if self.check_cookie_status():
			for user_twit in Twit.objects.filter(author=self.request.user).order_by('-posted_on')[:10]:
				if user_twit.content and keyword.lower() in user_twit.content.lower():
					return ("<p>GDPR compliance is important. "
							"Check out the latest <a target=\"_blank\" "
							"href=\"https://academic.oup.com/book/41324\">"
							"GDPR commentary</a>.</p>")
		return ("<p>Love cooking? "
				"Check out the latest <a target=\"_blank\" "
				"href=\"https://www.bettybossi.ch/de/shop/produkt/the-swiss-cookbook-kochbuch-27048/\">"
				"Swiss cuisine handbook</a>.</p>")

	def get_context_data(self, **kwargs):

		followed_users = list(Follow.objects.filter(follower=self.request.user).values_list('following', flat=True))
		followed_users.append(self.request.user)
		twits = Twit.objects.filter(author__in=followed_users).order_by('-posted_on')[:10]
		
		return {'title'           : 'Your Minitwit home', 
		        'twits'           : twits, 
			'post_form'       : TwitForm,  
			'advertisement'   : self.generate_advertisement(),
			'accepted_cookie' : self.check_cookie_status()}
		
	def check_cookie_status(self):
		return self.request.COOKIES.get('cookie_consent') == 'true'


class FollowUserView(LoginRequiredMixin, CreateView):
	"""Follow a user
	1. In get method returns all user list
	2. In post method follow an user
	"""

	def get(self, request, *args, **kwargs):
		following_list = list(Follow.objects.filter(follower=request.user).values_list('following').values_list('pk',
		                                                                                                        flat=True))
		following_list.append(request.user.pk)
		# remove all users that I am following
		users = User.objects.exclude(pk__in=following_list)
		return TemplateResponse(request, 'follow.html', {'user_list': users})

	def post(self, request, *args, **kwargs):
		user = get_object_or_404(User, pk=request.POST.get('pk'))

		# Direct follow no notification etc
		# Here AJAX request can be used to optimize the db query

		Follow(follower=request.user, following=user).save()

		# redirect to home page
		return redirect('/')


class AccountProfileView(TemplateView):
	"""Display a user profile

	"""

	template_name = 'account_profile.html'

	def get(self, request, *args, **kwargs):
		context = dict()
		context['user'] = request.user
		return TemplateResponse(request, self.template_name, context)


class FollowListView(LoginRequiredMixin, TemplateView):
	"""List of the user that I am following

	"""
	template_name = "following.html"

	def get_context_data(self, **kwargs):
		followings = Follow.objects.filter(follower=self.request.user).values_list('following', flat=True)
		followings = User.objects.filter(pk__in=followings)
		return {'following_list': followings}


class MyTwitsView(LoginRequiredMixin, TemplateView):
	"""Display all twits made by me

	"""
	template_name = 'my_twits.html'

	def get_context_data(self, **kwargs):
		return {'twit_list': Twit.objects.filter(author=self.request.user)}


class SignUpView(FormView):
	"""Signup a user
	1. In get return a signup form
	2. In post method verify user data and create an user
	"""
	template_name = 'registration/signup.html'

	def get(self, request, *args, **kwargs):
		if request.user.is_authenticated:
			return redirect('/')
		form = SignUpForm()
		return TemplateResponse(request, self.template_name, {'form': form})

	def post(self, request, *args, **kwargs):
		form = SignUpForm(request.POST)
		if form.is_valid():
			form.save()
			return redirect('login')
		return TemplateResponse(request, self.template_name, {'form': form})


class PostTwitView(LoginRequiredMixin, FormView):
	"""Post a twit
	GET method is not allowed so 404
	"""

	def get(self, request, *args, **kwargs):
		raise Http404

	def post(self, request, *args, **kwargs):
		twit_form = TwitForm(request.POST)
		if twit_form.is_valid():

			# Save twit in main DB
			twit_form.instance.author = request.user
			twit_form.save()
			# twit.author = request.user


			# Save twit in Redis DB for fast retrieval in the form of list
			# currently pipe(|) is used as separator
			# TODO split list if size grows then certain limit
			# TODO use some other symbol for separator or use escaping technique
			# TODO If we found that this is taking more than exec a process here and let them do this

			conn = redis.StrictRedis(host='localhost', port=6379, db=0)
			followings = Follow.objects.filter(follower=request.user).values_list('following', flat=True)
			msg = "%s|%s|%s" % (request.user, now(), twit_form.cleaned_data['content'])
			for fol in followings:
				conn.lpush(fol, msg)
		else:
			print(twit_form.errors)
		return redirect('/')


class EditTwitView(LoginRequiredMixin, UpdateView):
	"""
	Edit a twit
	"""
	template_name = 'edit_twit.html'

	def get(self, request, *args, **kwargs):
		twit = self.get_twit(request, **kwargs)
		if isinstance(twit, HttpResponse):
			return twit
		form = TwitForm(instance=twit)
		return TemplateResponse(request, self.template_name, {'form': form})

	def post(self, request, *args, **kwargs):

		twit = self.get_twit(request, **kwargs)
		if isinstance(twit, HttpResponse):
			return twit

		form = TwitForm(request.POST, instance=twit)

		# TODO update Redis DB

		if form.is_valid():
			form.save()
			return redirect('/')

		return TemplateResponse(request, self.template_name, {'form': form})

	def get_twit(self, request, **kwargs):
		"""Retrieve a twit from DB and check twit permission
		if requester has permission to edit twit then return
		else return to home page(without any error)
		"""

		pk = kwargs.get('pk')
		twit = get_object_or_404(Twit, pk=pk)

		if twit.author != request.user:
			return redirect('/')
		return twit



def custom_logout(request):
	"""
	Logout an user and redirect to home page
	"""
	logout(request)
	return redirect('/')

class SetCookieConsentView(View):
	def post(self, request, *args, **kwargs):
		next_url = request.POST.get('next', '/')
		response = redirect(next_url)
		if 'accept' in request.POST:
			response.set_cookie('cookie_consent', 'true', max_age=365*24*60*60)  # Set for one year
		elif 'decline' in request.POST:
			response.set_cookie('cookie_consent', 'false', max_age=365*24*60*60)
		else:
			return HttpResponseBadRequest("Invalid request")
		return response
    
@login_required
def delete_twit(request, pk):
    return redirect('/')
