def cookie_consent(request):

    return {'show_cookie_banner': not request.COOKIES.get('cookie_consent'), 
            'accepted_cookie': request.COOKIES.get('cookie_consent') == 'true'}