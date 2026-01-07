from django.http import HttpResponseRedirect

from epl.services.tenant import get_front_domain


def home(request):
    url = get_front_domain(request) + "/"
    return HttpResponseRedirect(url)
