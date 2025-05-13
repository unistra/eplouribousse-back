from django.urls import path

from epl.apps.project import views

urlpatterns = [
    path("user-projects/", views.user_projects, name="user_projects"),
    path("manage-project/", views.manage_project, name="manage_project"),
    path("manage-project/<int:project_id>/", views.manage_project, name="manage_project"),
]
