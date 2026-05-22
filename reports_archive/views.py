from django.views import View
from django.shortcuts import render
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.shortcuts import redirect

class ExportDataView(LoginRequiredMixin, View):

    login_url = 'doctor:login'

    def dispatch(self, request, *args, **kwargs):

        if request.user.innermember.role != 'doctor':

            messages.error(request,'Access denied.')

            return redirect('doctor:dashboard')

        return super().dispatch(request, *args, **kwargs)

    def get(self, request):

        context = {}

        return render(request,'reports_archive/export_data.html',context)


class ArchiveRecordsView(LoginRequiredMixin, View):

    login_url = 'doctor:login'

    def dispatch(self, request, *args, **kwargs):

        if request.user.innermember.role != 'doctor':

            messages.error(request,'Access denied.')

            return redirect('doctor:dashboard')

        return super().dispatch(request, *args, **kwargs)

    def get(self, request):

        return render(request,'reports_archive/archive_records.html')