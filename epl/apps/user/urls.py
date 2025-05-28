from django.urls import path
from rest_framework.routers import DefaultRouter

from epl.apps.user import views

router = DefaultRouter()
router.register(r"", views.UserViewSet, basename="user")

urlpatterns = router.urls

urlpatterns += [
    # path("", views.UserViewSet.as_view({"get": "list"}), name="list_users"),
    path("change-password/", views.change_password, name="change_password"),
    path("reset-password/", views.reset_password, name="reset_password"),
    path("send-reset-email/", views.send_reset_email, name="send_reset_email"),
    path("login-success/", views.login_success, name="login_success"),
    path("login-handshake/", views.login_handshake, name="login_handshake"),
    path("profile/", views.user_profile, name="user_profile"),
    path("invite/", views.invite, name="invite"),
    path("invite-handshake/", views.invite_handshake, name="invite_handshake"),
    path("create-account/", views.create_account, name="create_account"),
    path("profile/", views.user_profile, name="user"),
]
