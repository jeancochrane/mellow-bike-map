from django.db import connection
from django.urls import reverse_lazy
from django.shortcuts import render
from django.views.generic import TemplateView, CreateView, UpdateView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer

from mellow_bike_map.models import MellowWay, fetchall
from mellow_bike_map.forms import MellowWayCreateForm, MellowWayEditForm


class Home(TemplateView):
    title = 'Home'
    template_name = 'mellow_bike_map/index.html'


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
                        FROM mellow_bike_map_mellowway
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


class MellowWayList(LoginRequiredMixin, ListView):
    title = 'Mellow Ways'
    model = MellowWay
    template_name = 'mellow_bike_map/mellow_way_list.html'


class MellowWayCreate(LoginRequiredMixin, CreateView):
    title = 'Create Mellow Way'
    template_name = 'mellow_bike_map/mellow_way_create.html'
    form_class = MellowWayCreateForm
    model = MellowWay
    success_url = reverse_lazy('mellow-way-list')


class MellowWayEdit(LoginRequiredMixin, UpdateView):
    title = 'Edit Mellow Way'
    template_name = 'mellow_bike_map/mellow_way_edit.html'
    form_class = MellowWayEditForm
    model = MellowWay
    success_url = reverse_lazy('mellow-way-list')


def page_not_found(request, exception, template_name='mellow_bike_map/404.html'):
    return render(request, template_name, status=404)


def server_error(request, template_name='mellow_bike_map/500.html'):
    return render(request, template_name, status=500)
