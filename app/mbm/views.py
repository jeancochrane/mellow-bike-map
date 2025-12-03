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
from mbm.routing import calculate_route


# osm2pgrouting tag IDs for indexing specific types of streets. For docs, see:
# https://github.com/pgRouting/osm2pgrouting/blob/8491929fc4037d308f271e84d59bb96da3c28aa2/mapconfig_for_bicycles.xml


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
        features, distance, time = calculate_route(source_vertex_id, target_vertex_id, enable_v2)
        directions = directions_list(features)

        # need to adapt to not take rows
        # major_streets = self.get_major_streets(rows, dist_in_meters)
        major_streets = []

        return {
            'type': 'FeatureCollection',
            'properties': {
                'distance': distance,
                'time': time,
                'major_streets': major_streets,
            },
            'features': features,
            'directions': directions,
        }

    def get_major_streets(self, rows, total_length):
        min_percentage = 0.2 # minimum percentage of the total length of the route that a street must cover to be considered major
        max_results = 3

        if not total_length:
            return []

        per_street_lengths = {}
        for row in rows:
            name = row.get('name')
            length = row.get('length_m') or 0
            if not name:
                continue
            per_street_lengths[name] = per_street_lengths.get(name, 0) + length

        threshold = total_length * min_percentage
        qualifying = [
            (name, length)
            for name, length in per_street_lengths.items()
            if length > threshold
        ]
        qualifying.sort(key=lambda item: (-item[1], item[0]))

        return [name for name, _ in qualifying[:max_results]]



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
