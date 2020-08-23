"""example_app URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.0/topics/http/urls/
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
from django.urls import path

from mellow_bike_map import views

urlpatterns = [
    path('', views.Home.as_view(), name='home'),
    path('api/route/', views.Route.as_view(), name='route'),
    path('ways/', views.MellowWayList.as_view(), name='mellow-way-list'),
    path('ways/create/', views.MellowWayCreate.as_view(), name='mellow-way-create'),
    path('ways/edit/<slug:slug>/', views.MellowWayEdit.as_view(), name='mellow-way-edit'),
    path('admin/', admin.site.urls),
]

handler404 = 'mellow_bike_map.views.page_not_found'
handler500 = 'mellow_bike_map.views.server_error'
