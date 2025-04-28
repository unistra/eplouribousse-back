from django.urls import path

from .views import change_password

urlpatterns = [
    path("change-password/", change_password, name="change_password"),
    path("reset-password/", reset_password, name="reset_password"),
    path("send-reset-email/", send_reset_email, name="send_reset_email"),
    path("login-success/", login_success, name="login_success"),
]
