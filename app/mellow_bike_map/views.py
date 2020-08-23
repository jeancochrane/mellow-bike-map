from django.db import connection
from django.shortcuts import render
from django.views.generic import TemplateView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer


class Home(TemplateView):
    title = 'Home'
    template_name = 'mellow_bike_map/index.html'


class Route(APIView):
    renderer_classes = [JSONRenderer]

    def get(self, request):
        source, target = self.get_source(request), self.get_target(request)
        route = self.get_route(source, target)
        data = {
            'source': source,
            'target': target,
            'geom': route['geom'],
            'cost': route['cost']
        }
        return Response(data)

    def get_source(self, request):
        return int(request.GET.get('source'))

    def get_target(self, request):
        return int(request.GET.get('target'))

    def get_route(self, source, target):
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT ST_AsGeoJSON(ST_Union(nodes, ways)) AS geom, cost
                FROM (
                    SELECT
                        ST_Union(node.the_geom) AS nodes,
                        ST_Union(way.the_geom) AS ways,
                        MAX(path.agg_cost) AS cost
                    FROM pgr_dijkstra(
                        'SELECT gid AS id, source, target, cost, reverse_cost FROM chicago_ways',
                        %s,
                        %s
                    ) AS path
                    JOIN chicago_ways AS way
                    ON path.edge = way.gid
                    JOIN chicago_ways_vertices_pgr AS node
                    on path.node = node.id
                ) AS route
            """, [source, target])
            rows = self.fetchall(cursor)
        return rows[0]

    def fetchall(self, cursor):
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


def page_not_found(request, exception, template_name='mellow_bike_map/404.html'):
    return render(request, template_name, status=404)


def server_error(request, template_name='mellow_bike_map/500.html'):
    return render(request, template_name, status=500)
