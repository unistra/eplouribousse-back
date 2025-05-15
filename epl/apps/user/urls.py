from django.urls import path

from epl.apps.user import views

urlpatterns = [
    path("", views.UserViewSet.as_view({"get": "list"}), name="list_users"),
    path("change-password/", views.change_password, name="change_password"),
    path("reset-password/", views.reset_password, name="reset_password"),
    path("send-reset-email/", views.send_reset_email, name="send_reset_email"),
    path("login-success/", views.login_success, name="login_success"),
    path("login-handshake/", views.login_handshake, name="login_handshake"),
    path("profile/", views.user_profile, name="user"),
]
