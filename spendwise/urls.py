"""
URL configuration for spendwise project.
"""
from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('favicon.ico', lambda request: HttpResponse(status=204)),
    path('admin/', admin.site.urls),
    path('', include('tracker.urls')),
]

if settings.DEBUG and settings.STATICFILES_DIRS:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
