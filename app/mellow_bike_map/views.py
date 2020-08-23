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
            rows = self.fetchall(cursor)
        return rows[0]['id']

    def fetchall(self, cursor):
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_route(self, source_vertex_id, target_vertex_id):
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
            """, [source_vertex_id, target_vertex_id])
            rows = self.fetchall(cursor)
        return rows[0]


def page_not_found(request, exception, template_name='mellow_bike_map/404.html'):
    return render(request, template_name, status=404)


def server_error(request, template_name='mellow_bike_map/500.html'):
    return render(request, template_name, status=500)
