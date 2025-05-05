from django.contrib import admin
from django.urls import path, include
from appointments import urls as appointments_urls
from therapists import urls as therapists_urls
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('appointments/', include(appointments_urls)),
    path('therapists/', include(therapists_urls)),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
