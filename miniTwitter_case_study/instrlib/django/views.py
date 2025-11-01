from instrlib.django.custom_http import redirect, render

def error_redirect_view(*args, **kwargs):
    # print(f'args[1]: {args[1]}')
    return

def error_page_view(request, *args, **kwargs):
    context = {
        'error_args'   : args,
        'error_details': kwargs  # Pass the entire kwargs dictionary to the template
    }
    return render(request, 'error_page.html', context)
