import json

from django.db import connection
from django.urls import reverse_lazy
from django.shortcuts import render
from django.views.generic import TemplateView, CreateView, UpdateView, ListView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer

from mbm.models import MellowRoute, fetchall
from mbm.forms import MellowRouteCreateForm, MellowRouteEditForm


class Home(TemplateView):
    title = 'Home'
    template_name = 'mbm/index.html'


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
    title = 'Mellow Ways'
    model = MellowRoute
    template_name = 'mbm/mellow_route_list.html'

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['regions'] = json.dumps({
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
    title = 'Create Mellow Way'
    template_name = 'mbm/mellow_route_create.html'
    form_class = MellowRouteCreateForm
    model = MellowRoute
    success_url = reverse_lazy('mellow-route-list')


class MellowRouteEdit(LoginRequiredMixin, UpdateView):
    title = 'Edit Mellow Way'
    template_name = 'mbm/mellow_route_edit.html'
    form_class = MellowRouteEditForm
    model = MellowRoute
    success_url = reverse_lazy('mellow-route-list')


class MellowRouteDelete(LoginRequiredMixin, DeleteView):
    title = 'Delete Mellow Way'
    template_name = 'mbm/mellow_route_confirm_delete.html'
    model = MellowRoute
    success_url = reverse_lazy('mellow-route-list')


def page_not_found(request, exception, template_name='mbm/404.html'):
    return render(request, template_name, status=404)


def server_error(request, template_name='mbm/500.html'):
    return render(request, template_name, status=500)
