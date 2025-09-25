from django.urls import path
from rest_framework_nested.routers import NestedSimpleRouter, SimpleRouter

from epl.apps.project.views.collection import CollectionViewSet
from epl.apps.project.views.library import LibraryViewset
from epl.apps.project.views.project import ProjectAlertSettingsAPIView, ProjectViewSet
from epl.apps.project.views.projectlibrary import ProjectLibraryViewSet
from epl.apps.project.views.resource import ResourceViewSet
from epl.apps.project.views.segment import SegmentViewSet

router = SimpleRouter()
router.register(r"projects", ProjectViewSet, basename="project")
router.register(r"libraries", LibraryViewset, basename="library")
router.register(r"collections", CollectionViewSet, basename="collection")
router.register(r"resources", ResourceViewSet, basename="resource")
router.register(r"segments", SegmentViewSet, basename="segment")

projects_router = NestedSimpleRouter(router, r"projects", lookup="project")
projects_router.register(r"libraries", ProjectLibraryViewSet, basename="projects-library")

urlpatterns = router.urls + projects_router.urls

urlpatterns += [
    path(
        "projects/<uuid:project_pk>/alert-settings/",
        ProjectAlertSettingsAPIView.as_view(),
        name="project-alert-settings-singleton",
    ),
]
