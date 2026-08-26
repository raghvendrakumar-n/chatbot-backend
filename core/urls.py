"""Root URL configuration for the core project."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from api.views import health, root

urlpatterns = [
    path("", root),
    path("admin/", admin.site.urls),
    path("api/health", health),
    path("api/", include("api.urls")),
]

# Serve uploaded media (logos, avatars) in development.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
