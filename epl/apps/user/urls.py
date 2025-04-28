from django.urls import path

from .views import change_password

urlpatterns = [
    path("user/change-password/", change_password, name="change_password"),
]
