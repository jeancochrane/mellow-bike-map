import json

from django.db import connection
from django.urls import reverse_lazy
from django.shortcuts import render
from django.http import HttpResponseRedirect, HttpResponse
from django.views.generic import TemplateView, CreateView, UpdateView, ListView, DeleteView
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer
from rest_framework.exceptions import ParseError

from mbm import forms
from mbm.models import MellowRoute, fetchall
from mbm.directions import directions_list


# osm2pgrouting tag IDs for indexing specific types of streets. For docs, see:
# https://github.com/pgRouting/osm2pgrouting/blob/8491929fc4037d308f271e84d59bb96da3c28aa2/mapconfig_for_bicycles.xml

RESIDENTIAL_STREET_TAG_IDS = (
    507,  # living_street
    509,  # residential
)

CYCLEWAY_TAG_IDS = (
    101,  # cycleway:track
    201,  # cycleway:right:track
    301,  # cycleway:left:track
    501,  # highway:cycleway
)


class Home(TemplateView):
    title = 'Home'
    template_name = 'mbm/index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Pass from/to addresses from URL if they exist
        context['from_address'] = kwargs.get('from_address', '')
        context['to_address'] = kwargs.get('to_address', '')
        return context


class About(TemplateView):
    title = 'About'
    template_name = 'mbm/about.html'


class RouteList(APIView):
    renderer_classes = [JSONRenderer]

    def get(self, request):
        return Response(MellowRoute.all())


class Route(APIView):
    renderer_classes = [JSONRenderer]

    def get(self, request):
        source_coord = self.get_coord_from_request(request, 'source')
        source_vertex_id = self.get_nearest_vertex_id(source_coord)

        target_coord = self.get_coord_from_request(request, 'target')
        target_vertex_id = self.get_nearest_vertex_id(target_coord)

        enable_v2 = request.GET.get("enable_v2", False) == "true"

        return Response({
            'source': source_coord,
            'target': target_coord,
            'source_vertex_id': source_vertex_id,
            'target_vertex_id': target_vertex_id,
            'route': self.get_route(source_vertex_id, target_vertex_id, enable_v2)
        })

    def get_coord_from_request(self, request, key):
        try:
            coord = request.GET[key]
        except KeyError:
            raise ParseError('Request is missing required key: %s' % key)

        coord_parts = coord.split(',')

        try:
            assert len(coord_parts) == 2
            float(coord_parts[0]), float(coord_parts[1])
        except (AssertionError, TypeError):
            raise ParseError(
                "Request argument '%s' must be a coordinate of the form lng,lat" % key
            )

        return coord_parts

    def get_nearest_vertex_id(self, coord):
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT vert.id
                FROM chicago_ways_vertices_pgr AS vert
                ORDER BY vert.the_geom <-> ST_SetSRID(
                    ST_MakePoint(%s, %s),
                    4326
                )
                LIMIT 1
            """, [coord[1], coord[0]])  # ST_MakePoint() expects lng,lat
            rows = fetchall(cursor)
        if rows:
            return rows[0]['id']
        else:
            raise ParseError('No vertex found near point %s' % ','.join(coord))

    def get_route(self, source_vertex_id, target_vertex_id, enable_v2=False):
        with connection.cursor() as cursor:
            cursor.execute(f"""
                SELECT
                    way.name,
                    way.gid,
                    way.length_m,
                    ST_AsGeoJSON(oriented.the_geom) AS geometry,
                    -- Calculate the angle between each segment of the route so we can generate turn-by-turn directions
                    DEGREES(ST_AZIMUTH(ST_StartPoint(oriented.the_geom), ST_EndPoint(oriented.the_geom))) AS heading,
                    mellow.type,
                    path.seq,
                    -- Additional OSM data for debugging
                    way.osm_id,
                    way.tag_id,
                    way.oneway,
                    way.rule,
                    way.priority,
                    way.maxspeed_forward,
                    way.maxspeed_backward,
                    osm_way.tags,
                    way.park_name
                FROM pgr_dijkstra(
                    'WITH mellow AS (
                        SELECT DISTINCT(UNNEST(ways)) AS osm_id, type
                        FROM mbm_mellowroute
                    )
                    SELECT
                        way.gid AS id,
                        way.source,
                        way.target,
                        CASE
                            WHEN mellow.type = ''path'' THEN way.cost * 0.1
                            {f"WHEN way.tag_id in {CYCLEWAY_TAG_IDS} THEN way.cost * 0.1" if enable_v2 is True else ""}
                            WHEN mellow.type = ''street'' THEN way.cost * 0.25
                            {f"WHEN way.tag_id in {RESIDENTIAL_STREET_TAG_IDS} THEN way.cost * 0.25" if enable_v2 is True else ""}
                            WHEN way.oneway = ''YES'' THEN way.cost * 0.5
                            WHEN mellow.type = ''route'' THEN way.cost * 0.75
                            ELSE way.cost
                        END AS cost,
                        CASE
                            WHEN mellow.type = ''path'' THEN way.reverse_cost * 0.1
                            {f"WHEN way.tag_id in {CYCLEWAY_TAG_IDS} THEN way.cost * 0.1" if enable_v2 is True else ""}
                            WHEN mellow.type = ''street'' THEN way.reverse_cost * 0.25
                            {f"WHEN way.tag_id in {RESIDENTIAL_STREET_TAG_IDS} THEN way.cost * 0.25" if enable_v2 is True else ""}
                            WHEN way.oneway = ''YES'' THEN way.reverse_cost * 0.5
                            WHEN mellow.type = ''route'' THEN way.reverse_cost * 0.75
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
                LEFT JOIN (
                    SELECT DISTINCT(UNNEST(ways)) AS osm_id, type
                    FROM mbm_mellowroute
                ) as mellow
                USING(osm_id)
                LEFT JOIN osm_ways AS osm_way
                ON way.osm_id = osm_way.osm_id,
                -- Make sure each segment of the route is oriented such that the last point of
                -- each line segment is the same as the first point in the next line segment
                LATERAL (
                    SELECT CASE
                        WHEN path.node = way.source THEN way.the_geom
                        ELSE ST_Reverse(way.the_geom)
                    END AS the_geom
                ) as oriented
                ORDER BY path.seq
            """, [source_vertex_id, target_vertex_id])
            rows = fetchall(cursor)

        # Calculate total distance in miles and time in minutes based on
        # the total length of the route in meters
        dist_in_meters = sum(row['length_m'] for row in rows)
        distance, time = self.format_distance(dist_in_meters)

        # Build features list
        features = [
            {
                'type': 'Feature',
                'geometry': json.loads(row['geometry']),
                'properties': {
                    'name': row['name'],
                    'type': row['type'],
                    'distance': row['length_m'],
                    'heading': row['heading'],
                    'gid': row['gid'],
                    # OSM debugging data
                    'osm_id': row['osm_id'],
                    'tag_id': row['tag_id'],
                    'oneway': row['oneway'],
                    'rule': row['rule'],
                    'priority': row['priority'],
                    'maxspeed_forward': row['maxspeed_forward'],
                    'maxspeed_backward': row['maxspeed_backward'],
                    'osm_tags': row['tags'],
                    'park_name': row['park_name'],
                }
            }
            for row in rows
        ]

        # Generate turn-by-turn directions
        directions = directions_list(features)

        return {
            'type': 'FeatureCollection',
            'properties': {
                'distance': distance,
                'time': time,
            },
            'features': features,
            'directions': directions,
        }

    def format_distance(self, dist_in_meters):
        """
        Given a distance in meters, return a tuple (distance, time)
        where `distance` is a string representing a distance in miles and
        `time` is a string representing an estimated travel time in minutes.
        """
        meters_per_mi = 1609.344
        dist_in_mi = dist_in_meters / meters_per_mi
        formatted_dist = round(dist_in_mi, 1)
        # Don't worry about single-mile case since we always report at least
        # one decimal (i.e. "1.0 miles")
        dist_unit_str = 'miles'
        distance = f'{formatted_dist} {dist_unit_str}'

        # Assume 8mph as a naive guess of speed
        mi_per_min = 10 / 60
        time_in_min = dist_in_mi / mi_per_min
        formatted_time = '<1' if time_in_min < 1 else str(round(time_in_min))
        time_unit_str = 'minute' if formatted_time in ['<1', '1'] else 'minutes'
        time = f'{formatted_time} {time_unit_str}'

        return distance, time


class OsmWay(APIView):
    """
    API endpoint to fetch the complete geometry of an OSM way by osm_id.
    This returns the full street/path geometry from the osm_ways table,
    which may extend beyond the route segments.
    """
    renderer_classes = [JSONRenderer]

    def get(self, request):
        osm_id = request.GET.get('osm_id')
        
        if not osm_id:
            raise ParseError('Request is missing required parameter: osm_id')
        
        try:
            osm_id = int(osm_id)
        except (ValueError, TypeError):
            raise ParseError('osm_id must be an integer')
        
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    osm_id,
                    name,
                    ST_AsGeoJSON(the_geom) AS geometry
                FROM osm_ways
                WHERE osm_id = %s
            """, [osm_id])
            
            row = cursor.fetchone()
            
            if not row:
                return Response({
                    'error': f'No OSM way found with osm_id {osm_id}'
                }, status=404)
            
            columns = [col[0] for col in cursor.description]
            result = dict(zip(columns, row))
        
        return Response({
            'type': 'Feature',
            'geometry': json.loads(result['geometry']),
            'properties': {
                'osm_id': result['osm_id'],
                'name': result['name']
            }
        })


class ParkBoundaries(LoginRequiredMixin, APIView):
    """
    API endpoint to fetch Chicago park boundaries as GeoJSON.
    """
    renderer_classes = [JSONRenderer]

    def get(self, request):
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    park,
                    ST_AsGeoJSON(wkb_geometry) AS geometry
                FROM chicago_parks
                WHERE park IS NOT NULL
                ORDER BY park
            """)
            rows = fetchall(cursor)
        
        return Response({
            'type': 'FeatureCollection',
            'features': [
                {
                    'type': 'Feature',
                    'geometry': json.loads(row['geometry']),
                    'properties': {
                        'name': row['park']
                    }
                }
                for row in rows
            ]
        })


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


def pong(request):
    from django.http import HttpResponse

    try:
        from .deployment import DEPLOYMENT_ID
    except ImportError as e:
        return HttpResponse('Bad deployment: {}'.format(e), status=401)

    return HttpResponse(DEPLOYMENT_ID)


def healthcheck(request):
    """Simple endpoint to test database connectivity."""
    with connection.cursor() as cursor:
        cursor.execute("""SELECT 1""")
    return HttpResponse("")
