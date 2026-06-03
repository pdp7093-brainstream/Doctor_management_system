from django.shortcuts import render


def custom_404(request, exception):
    """Custom 404 - Page Not Found"""
    return render(request, '404.html', status=404)


def custom_500(request):
    """Custom 500 - Server Error"""
    return render(request, '500.html', status=500)


def custom_403(request, exception):
    """Custom 403 - Forbidden"""
    return render(request, '403.html', status=403)
