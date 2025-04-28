from django.contrib import admin
from django.urls import path

from epl.apps.tenant.views import consortium_info

admin.autodiscover()

urlpatterns = [
    path("consortium/", consortium_info, name="consortium"),
]
