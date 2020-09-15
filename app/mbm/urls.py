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

from mbm import views

urlpatterns = [
    path('', views.Home.as_view(), name='home'),
    path('api/route/', views.Route.as_view(), name='route'),
    path('api/routes/', views.RouteList.as_view(), name='route-list'),
    path('neighborhoods/', views.MellowRouteList.as_view(), name='mellow-route-list'),
    path('neighborhoods/create/', views.MellowRouteCreate.as_view(), name='mellow-route-create'),
    path('neighborhoods/edit/<slug:slug>/', views.MellowRouteNeighborhoodEdit.as_view(), name='mellow-route-neighborhood-edit'),
    path('neighborhoods/edit/<slug:slug>/<str:type>/', views.MellowRouteEdit.as_view(), name='mellow-route-edit'),
    path('neighborhoods/delete/<slug:slug>/', views.MellowRouteDelete.as_view(), name='mellow-route-delete'),
    path('admin/', admin.site.urls),
    path('pong/', views.pong),
]

handler404 = 'mbm.views.page_not_found'
handler500 = 'mbm.views.server_error'
