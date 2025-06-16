from rest_framework.routers import DefaultRouter

from epl.apps.project.views.collection import CollectionViewSet
from epl.apps.project.views.library import LibraryViewset
from epl.apps.project.views.project import ProjectViewSet

router = DefaultRouter()
router.register(r"projects", ProjectViewSet, basename="project")
router.register(r"libraries", LibraryViewset, basename="library")
router.register(r"collections", CollectionViewSet, basename="collection")
urlpatterns = router.urls
