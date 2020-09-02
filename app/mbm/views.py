import json

from django.db import connection
from django.urls import reverse_lazy
from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.views.generic import TemplateView, CreateView, UpdateView, ListView, DeleteView
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer

from mbm import forms
from mbm.models import MellowRoute, fetchall


class Home(TemplateView):
    title = 'Home'
    template_name = 'mbm/index.html'


class RouteList(APIView):
    renderer_classes = [JSONRenderer]

    def get(self, request):
        return Response(MellowRoute.all())


class Route(APIView):
    renderer_classes = [JSONRenderer]

    def get(self, request):
        source_osm_id = self.get_value_from_request(request, 'source')
        source_vertex_id = self.get_nearest_vertex_id(source_osm_id)

        target_osm_id = self.get_value_from_request(request, 'target')
        target_vertex_id = self.get_nearest_vertex_id(target_osm_id)

        route = self.get_route(source_vertex_id, target_vertex_id)
        data = {
            'source': source_osm_id,
            'target': target_osm_id,
            'source_vertex_id': source_vertex_id,
            'target_vertex_id': target_vertex_id,
            'geom': route['geom'],
            'cost': route['cost']
        }
        return Response(data)

    def get_value_from_request(self, request, key):
        try:
            return request.GET[key]
        except KeyError:
            raise KeyError('Request is missing required key: %s' % key)

    def get_nearest_vertex_id(self, osm_id):
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT (
                    SELECT vert.id
                    FROM chicago_ways_vertices_pgr AS vert
                    ORDER BY osm_nodes.the_geom <-> vert.the_geom
                    LIMIT 1
                )
                FROM osm_nodes
                WHERE osm_id = %s
            """, [osm_id])
            rows = fetchall(cursor)
        return rows[0]['id']

    def get_route(self, source_vertex_id, target_vertex_id):
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    ST_AsGeoJSON(ST_Union(way.the_geom)) AS geom,
                    MAX(path.agg_cost) AS cost
                FROM pgr_dijkstra(
                    'WITH mellow AS (
                        SELECT DISTINCT(UNNEST(ways)) AS osm_id, slug
                        FROM mbm_mellowroute
                    )
                    SELECT
                        way.gid AS id,
                        way.source,
                        way.target,
                        CASE
                            WHEN mellow.slug IS NOT NULL
                            THEN way.cost * 0.1
                            ELSE way.cost
                        END AS cost,
                        CASE
                            WHEN mellow.slug IS NOT NULL
                            THEN way.reverse_cost * 0.1
                            ELSE way.reverse_cost
                        END AS reverse_cost
                    FROM chicago_ways AS way
                    LEFT JOIN mellow
                    USING(osm_id)
                    ',
                    %s,
                    %s
                ) AS path
                JOIN chicago_ways AS way
                ON path.edge = way.gid
            """, [source_vertex_id, target_vertex_id])
            rows = fetchall(cursor)
        return rows[0]


class MellowRouteList(LoginRequiredMixin, ListView):
    title = 'Neighborhoods'
    model = MellowRoute
    queryset = MellowRoute.objects.values('name', 'slug').distinct('name', 'slug')
    template_name = 'mbm/mellow_route_list.html'

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['neighborhoods'] = json.dumps({
            'type': 'FeatureCollection',
            'features': [
                {
                    'type': 'Feature',
                    'geometry': json.loads(way.bounding_box.json),
                    'properties': {
                        'name': way.name
                    }
                }
                for way in self.model.objects.all()
            ]
        })
        return context


class MellowRouteCreate(LoginRequiredMixin, CreateView):
    title = 'Create Neighborhood'
    template_name = 'mbm/mellow_route_create.html'
    form_class = forms.MellowRouteCreateForm
    model = MellowRoute
    success_url = reverse_lazy('mellow-route-list')

    def form_valid(self, form):
        messages.success(self.request, 'Neighborhood created.')
        return super().form_valid(form)


class MellowRouteEdit(LoginRequiredMixin, UpdateView):
    title = 'Edit Neighborhood'
    template_name = 'mbm/mellow_route_edit.html'
    form_class = forms.MellowRouteEditForm
    model = MellowRoute
    success_url = reverse_lazy('mellow-route-list')

    def get_object(self):
        return self.model.objects.get(
            slug=self.kwargs['slug'],
            type=self.kwargs['type']
        )

    def form_valid(self, form):
        messages.success(self.request, 'Neighborhood updated.')
        return super().form_valid(form)


class MellowRouteNeighborhoodEdit(LoginRequiredMixin, UpdateView):
    title = 'Edit Neighborhood'
    template_name = 'mbm/mellow_route_edit.html'
    form_class = forms.MellowRouteNeighborhoodEditForm
    model = MellowRoute
    success_url = reverse_lazy('mellow-route-list')

    def get_object(self):
        # Get first object, since we don't care about the type
        return self.model.objects.filter(slug=self.kwargs['slug']).first()

    def form_valid(self, form):
        # Save the data for all MellowRoute types
        self.model.objects.filter(slug=self.kwargs['slug']).update(
            name=form.instance.name,
            slug=form.instance.slug,
            bounding_box=form.instance.bounding_box
        )
        return HttpResponseRedirect(self.success_url)


class MellowRouteDelete(LoginRequiredMixin, DeleteView):
    title = 'Delete Neighborhood'
    template_name = 'mbm/mellow_route_confirm_delete.html'
    model = MellowRoute
    success_url = reverse_lazy('mellow-route-list')

    def get_object(self):
        # We don't use the object type in the view, so just return the first
        # match on the slug
        return self.model.objects.filter(slug=self.kwargs['slug']).first()

    def delete(self, request, *args, **kwargs):
        # Delete all MellowRoutes with this slug, no matter the type
        self.model.objects.filter(slug=self.kwargs['slug']).delete()
        messages.success(self.request, 'Neighborhood deleted.')
        return HttpResponseRedirect(self.success_url)


def page_not_found(request, exception, template_name='mbm/404.html'):
    return render(request, template_name, status=404)


def server_error(request, template_name='mbm/500.html'):
    return render(request, template_name, status=500)
