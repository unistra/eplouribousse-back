from django.urls import path

from epl.apps.project import views

urlpatterns = [
    path("user-projects/", views.user_projects, name="user_projects"),
]
