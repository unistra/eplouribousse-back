from rest_framework.routers import DefaultRouter

from epl.apps.project.views.project import ProjectViewSet

router = DefaultRouter()
router.register(r"projects", ProjectViewSet, basename="project")
urlpatterns = router.urls
