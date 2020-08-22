from django.shortcuts import render
from django.views.generic import TemplateView


class Home(TemplateView):
    template_name = 'mellow_bike_map/index.html'


def page_not_found(request, exception, template_name='mellow_bike_map/404.html'):
    return render(request, template_name, status=404)


def server_error(request, template_name='mellow_bike_map/500.html'):
    return render(request, template_name, status=500)
