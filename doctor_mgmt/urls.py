"""
URL configuration for doctor_mgmt project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.views.static import serve

urlpatterns = [
    path('admin/', admin.site.urls),
    path('',include('accounts.urls')),
    path('doctor/', include(('doctor.urls', 'doctor'), namespace='doctor')),
    path('appointment/', include(('appointment.urls', 'appointment'), namespace='appointment')),
    path('medicine/', include(('medicine.urls', 'medicine'), namespace='medicine')),
    path('billing/', include(('billing.urls', 'billing'), namespace='billing')),
    path('clinic/', include(('clinic.urls', 'clinic'), namespace='clinic')),
    path('expenses/', include(('expenses.urls', 'expenses'), namespace='expenses')),
    path('reports/', include('reports_archive.urls', namespace='reports_archive')),

    # Serve static & media files (works with both DEBUG=True and DEBUG=False)
    re_path(r'^static/(?P<path>.*)$', serve, {'document_root': settings.STATICFILES_DIRS[0]}),
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]

# Custom error handlers — prevents Django from exposing URL patterns
handler404 = 'doctor_mgmt.views.custom_404'
handler500 = 'doctor_mgmt.views.custom_500'
handler403 = 'doctor_mgmt.views.custom_403'
