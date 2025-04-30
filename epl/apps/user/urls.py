from django.urls import path

from .views import change_password, reset_password, send_reset_email

urlpatterns = [
    path("change-password/", change_password, name="change_password"),
    path("reset-password/", reset_password, name="reset_password"),
    path("send-reset-email/", send_reset_email, name="send_reset_email"),
]
