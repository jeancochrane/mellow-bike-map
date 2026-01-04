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
        
        # Parse sidewalk_penalty if provided (default: 10.0 to discourage sidewalk routing)
        sidewalk_penalty = None
        if "sidewalk_penalty" in request.GET:
            try:
                sidewalk_penalty = float(request.GET.get("sidewalk_penalty"))
            except (ValueError, TypeError):
                raise ParseError("sidewalk_penalty must be a valid number")
        
        # Debug mode enables additional route statistics
        in_debug_mode = request.GET.get("debug", "false") == "true"
        
        return Response({
            'source': source_coord,
            'target': target_coord,
            'source_vertex_id': source_vertex_id,
            'target_vertex_id': target_vertex_id,
            'route': self.get_route(source_vertex_id, target_vertex_id, enable_v2, sidewalk_penalty, in_debug_mode)
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

    def build_cost_cases(self, cost_column, enable_v2, sidewalk_penalty):
        """
        Build the CASE expression for routing cost calculation.
        
        Routes are scored by multiplying path costs by preference weights:
        - Lower multipliers = more preferred routes
        - Higher multipliers = less preferred (penalized) routes
        
        Args:
            cost_column: Either 'cost' or 'reverse_cost'
            enable_v2: Whether to include v2 routing bonuses for cycleways/residential streets
            sidewalk_penalty: Multiplier to discourage sidewalk routing (e.g., 10.0 = 10x cost)
        """
        cases = []
        
        # Sidewalk penalty (optional) - discourage routing onto sidewalks
        if sidewalk_penalty is not None:
            # A way is considered a sidewalk if it has footway tags but lacks bicycle access
            is_sidewalk = """
                (osm_way.tags @> 'footway=>sidewalk'::hstore OR
                 osm_way.tags @> 'footway=>crossing'::hstore OR
                 osm_way.tags @> 'highway=>footway'::hstore)
                AND NOT
                (osm_way.tags @> 'bicycle=>permissive'::hstore OR
                 osm_way.tags @> 'bicycle=>yes'::hstore)
            """.replace("'", "''")  # Escape quotes for nested SQL string
            cases.append(f"WHEN ({is_sidewalk}) THEN way.{cost_column} * {sidewalk_penalty}")
        
        # Mellow paths (bike paths, trails) - strongly preferred
        cases.append(f"WHEN mellow.type = ''path'' THEN way.{cost_column} * 0.1")
        
        # v2: Dedicated cycleways - strongly preferred
        if enable_v2:
            cases.append(f"WHEN way.tag_id IN {CYCLEWAY_TAG_IDS} THEN way.{cost_column} * 0.1")
        
        # Mellow streets (quiet residential) - preferred
        cases.append(f"WHEN mellow.type = ''street'' THEN way.{cost_column} * 0.25")
        
        # v2: Residential streets - preferred
        if enable_v2:
            cases.append(f"WHEN way.tag_id IN {RESIDENTIAL_STREET_TAG_IDS} THEN way.{cost_column} * 0.25")
        
        # One-way streets - slightly preferred (predictable traffic)
        cases.append(f"WHEN way.oneway = ''YES'' THEN way.{cost_column} * 0.5")
        
        # Mellow routes (signed bike routes) - somewhat preferred
        cases.append(f"WHEN mellow.type = ''route'' THEN way.{cost_column} * 0.75")
        
        # Default: no preference adjustment
        cases.append(f"ELSE way.{cost_column}")
        
        return "CASE\n                            " + "\n                            ".join(cases) + "\n                        END"

    def get_route(self, source_vertex_id, target_vertex_id, enable_v2=False, sidewalk_penalty=None, in_debug_mode=False):
        """
        Calculate a route between two vertices.
        
        Args:
            source_vertex_id: Starting vertex ID
            target_vertex_id: Ending vertex ID
            enable_v2: Whether to use v2 routing algorithm
            sidewalk_penalty: Cost multiplier for sidewalks (None = no penalty)
            in_debug_mode: Whether to include debug info like sidewalk count
        """
        cost_case = self.build_cost_cases('cost', enable_v2, sidewalk_penalty)
        reverse_cost_case = self.build_cost_cases('reverse_cost', enable_v2, sidewalk_penalty)
        
        # Join with osm_ways table when we need access to hstore tags for sidewalk detection
        osm_ways_join = ""
        if sidewalk_penalty is not None:
            osm_ways_join = "LEFT JOIN osm_ways AS osm_way ON way.osm_id = osm_way.osm_id"
        
        with connection.cursor() as cursor:
            cursor.execute(f"""
                SELECT
                    way.osm_id,
                    way.name,
                    way.length_m,
                    ST_AsGeoJSON(way.the_geom) AS geometry,
                    mellow.type
                FROM pgr_dijkstra(
                    'WITH mellow AS (
                        SELECT DISTINCT(UNNEST(ways)) AS osm_id, type
                        FROM mbm_mellowroute
                    )
                    SELECT
                        way.gid AS id,
                        way.source,
                        way.target,
                        {cost_case} AS cost,
                        {reverse_cost_case} AS reverse_cost
                    FROM chicago_ways AS way
                    LEFT JOIN mellow
                    USING(osm_id)
                    {osm_ways_join}
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
            """, [source_vertex_id, target_vertex_id])
            rows = fetchall(cursor)

        # Calculate total distance in miles and time in minutes based on
        # the total length of the route in meters
        dist_in_meters = sum(row['length_m'] for row in rows)
        distance, time = self.format_distance(dist_in_meters)
        major_streets = self.get_major_streets(rows, dist_in_meters)

        properties = {
            'distance': distance,
            'time': time,
            'major_streets': major_streets,
        }
        
        # Only count sidewalks when debug mode is enabled (expensive query)
        if in_debug_mode:
            properties['sidewalk_count'] = self.count_sidewalk_ways(rows)

        return {
            'type': 'FeatureCollection',
            'properties': properties,
            'features': [
                {
                    'type': 'Feature',
                    'geometry': json.loads(row['geometry']),
                    'properties': {
                        'osm_id': row['osm_id'],
                        'name': row['name'],
                        'type': row['type']
                    }
                }
                for row in rows
            ]
        }

    def format_distance(self, dist_in_meters):
        """
        Given a distance in meters, return a tuple (distance, time)
        where `distance` is a string representing a distance in miles and
        `time` is a string representing an estimated travelime in minutes.
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

    def count_sidewalk_ways(self, rows):
        """
        Count the number of distinct sidewalk ways in a route.
        
        A way is considered a sidewalk if it has footway/sidewalk tags
        but lacks explicit bicycle access.
        """
        if not rows:
            return 0
        
        osm_ids = list(set(row['osm_id'] for row in rows if row.get('osm_id')))
        if not osm_ids:
            return 0
        
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(DISTINCT osm_way.osm_id)
                FROM osm_ways AS osm_way
                WHERE osm_way.osm_id = ANY(%s)
                AND (
                    osm_way.tags @> 'footway=>sidewalk'::hstore OR
                    osm_way.tags @> 'footway=>crossing'::hstore OR
                    osm_way.tags @> 'highway=>footway'::hstore
                )
                AND NOT (
                    osm_way.tags @> 'bicycle=>permissive'::hstore OR
                    osm_way.tags @> 'bicycle=>yes'::hstore
                )
            """, [osm_ids])
            row = cursor.fetchone()
            return row[0] if row else 0


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
