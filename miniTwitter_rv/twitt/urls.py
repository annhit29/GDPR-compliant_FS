"""""""""""""""""""""""""""""""""""""""""
# @author  sonus
# @date 02 - Apr - 2016
# @copyright sonus
# GitHub http://github.com/sonus21
"""""""""""""""""""""""""""""""""""""""""

from django.urls import path, re_path, include # type: ignore

from .views import DeleteAllView, SignUpView, FollowUserView, custom_logout, AccountProfileView,\
	PostTwitView, FollowListView, EditTwitView, HomeView, MyTwitsView, delete_twit, SetCookieConsentView
from django.contrib.auth.views import LoginView # type: ignore

urlpatterns = [

	path('', HomeView.as_view(), name='home'),

	path('accounts/profile/', AccountProfileView.as_view(), name='profile'),
	path('accounts/login/', LoginView.as_view(), name='login'),
	path('accounts/signup/', SignUpView.as_view(), name='signup'),
	path('accounts/logout/', custom_logout, name='logout'),

	path('accounts/twit/', MyTwitsView.as_view(), name='my_twits'),

	path('post/twit/', PostTwitView.as_view(), name='post_twit'),
	path('following/', FollowListView.as_view(), name='following_list'),
	re_path('edit/twit/(?P<pk>[0-9]+)/', EditTwitView.as_view(), name='edit_twit'),

	path('search/user/', FollowUserView.as_view(), name='follow_user'),
	path('search/twit/', include('haystack.urls')),
    path('twit/delete/<int:pk>/', delete_twit, name = 'delete_twit'),
    path('set-cookie-consent/', SetCookieConsentView.as_view(), name='set_cookie_consent'),
	path('delete/', DeleteAllView.as_view(), name='delete'),
	
]
