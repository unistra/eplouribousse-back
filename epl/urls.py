from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from epl.apps.tenant.views import consortium_info

from .views import home

admin.autodiscover()

urlpatterns = [
    # Examples:
    path("", home, name="home"),
    # path('app/', include('apps.app.urls')),
    path("admin/", admin.site.urls),
    # django-cas
    path("cas/", include("django_cas.urls", namespace="django_cas")),
    path("api/consortium/", consortium_info, name="consortium"),
    path("api/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/user/", include("epl.apps.user.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]

# debug toolbar for dev
if settings.DEBUG and "debug_toolbar" in settings.INSTALLED_APPS:
    import debug_toolbar

    urlpatterns += [
        path("__debug__/", include(debug_toolbar.urls)),
    ]
