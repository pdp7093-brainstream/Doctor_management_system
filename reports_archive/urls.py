from django.urls import path
from . import views

app_name = 'reports_archive'

urlpatterns = [

    path('export/',views.ExportDataView.as_view(),name='export_data'),

    path('archive/',views.ArchiveRecordsView.as_view(),name='archive_records'),

]