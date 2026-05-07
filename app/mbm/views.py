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

SIDEWALK_TAG_IDS = (
    503,  # highway:pedestrian
    504,  # highway:footway
)

# Illinois East coordinate system.
# Useful for geometry math since its units are in feet, as opposed to
# EPSG 4326's units of degree.
# See: https://epsg.io/3435
IL_EAST_CRS = 3435


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
        show_bbox = request.GET.get("show_bbox", False) == "true"

        response_dict = {
            'source': source_coord,
            'target': target_coord,
            'source_vertex_id': source_vertex_id,
            'target_vertex_id': target_vertex_id,
            'route': self.get_route(source_vertex_id, target_vertex_id, enable_v2, show_bbox = show_bbox)
        }
        return Response(response_dict)

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
            cursor.execute(f"""
                SELECT vert.id
                FROM chicago_ways_vertices_pgr AS vert
                INNER JOIN chicago_ways AS cw
                    ON vert.id = cw.source
                    OR vert.id = cw.target
                WHERE cw.tag_id NOT IN {SIDEWALK_TAG_IDS}
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

    def get_route(
        self,
        source_vertex_id,
        target_vertex_id,
        enable_v2=False,
        show_bbox=False
    ):
        """Get a GeoJSON feature collection representing a route between points
        `source_vertex_id` and `target_vertex_id`.

        Optional param behavior:

        - `enable_v2` (bool): Enable V2 routing (deprecated)
        - `show_bbox` (bool): Include the geometry of the bounding box that we
           use to restrict the search space in the feature collection in the
           response, along with a used_bbox` property indicating whether the
           bbox restriction was active for the returned route
        """
        # Make sure vertices are integers, since we need to template them
        # directly into the SQL string below to satisfy the pgRouting interface,
        # which means they are SQL injection targets
        assert isinstance(source_vertex_id, int)
        assert isinstance(target_vertex_id, int)

        rows = self._execute_route_query(
            source_vertex_id,
            target_vertex_id,
            enable_v2,
            use_bbox=True
        )
        used_bbox = True

        if not rows:
            rows = self._execute_route_query(
                source_vertex_id,
                target_vertex_id,
                enable_v2,
                use_bbox=False
            )
            used_bbox = False

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
        if show_bbox:
            properties['used_bbox'] = used_bbox

        route_geojson = {
            'type': 'FeatureCollection',
            'properties': properties,
            'features': [
                {
                    'type': 'Feature',
                    'geometry': json.loads(row['geometry']),
                    'properties': {
                        'name': row['name'],
                        'type': row['type']
                    }
                }
                for row in rows
            ]
        }

        if show_bbox and used_bbox:
            bbox_feature = self._execute_bbox_query(
                source_vertex_id,
                target_vertex_id
            )
            route_geojson["features"].append(bbox_feature)

        return route_geojson

    def _execute_route_query(
        self,
        source_vertex_id,
        target_vertex_id,
        enable_v2=False,
        use_bbox=True
    ):
        """Execute the routing query and return a list of rows representing
        steps of the route.

        Returns an empty list if no route was found.
        """
        query = self._build_route_query(
            source_vertex_id,
            target_vertex_id,
            enable_v2,
            use_bbox
        )
        with connection.cursor() as cursor:
            cursor.execute(query, [source_vertex_id, target_vertex_id])
            return fetchall(cursor)

    def _build_route_query(
        self,
        source_vertex_id,
        target_vertex_id,
        enable_v2=False,
        use_bbox=True
    ):
        """Build the SQL query for routing between two vertices.

        When `use_bbox` is True (default), the edge set is restricted to ways
        that intersect a buffered bounding box around the source and target, plus
        any tagged mellow 'path' ways (which are always included regardless of
        bounding box, to enable meandering along off-street paths that may
        veer outside the bounding box). When `use_bbox` is False, the routing
        algorithm will consider all ways.
        """
        assert isinstance(source_vertex_id, int)
        assert isinstance(target_vertex_id, int)

        if use_bbox:
            # One nuance to this query: When the bounding box is active, we
            # want to always include off-street "paths" regardless of whether
            # they are within the bounding box. To do this, we query two sets
            # of ways and union them: one that includes all ways that intersect
            # with the bounding box, and another that includes all off-street
            # path ways. It's important that we query these two sets of ways
            # separately and union them, since we want to make sure that PostGIS
            # can use the spatial index on `chicago_ways` for the bounding box
            # intersection, rather than performing a full table scan on
            # `chicago_ways` (which has 1m+ rows)
            edges_sql = f"""
                bbox AS (
                    {self._build_bbox_query(source_vertex_id, target_vertex_id)}
                ),
                edge AS (
                    SELECT
                        way.gid AS id,
                        way.source,
                        way.target,
                        way.cost,
                        way.reverse_cost,
                        way.oneway,
                        way.tag_id,
                        mellow.type
                    FROM chicago_ways AS way
                    JOIN bbox ON way.the_geom && bbox.geom
                    LEFT JOIN mellow USING(osm_id)
                    UNION
                    SELECT
                        way.gid AS id,
                        way.source,
                        way.target,
                        way.cost,
                        way.reverse_cost,
                        way.oneway,
                        way.tag_id,
                        mellow.type
                    FROM mellow
                    JOIN chicago_ways AS way USING(osm_id)
                    WHERE mellow.type = 'path'
                )
            """
        else:
            edges_sql = """
                edge AS (
                    SELECT
                        way.gid AS id,
                        way.source,
                        way.target,
                        way.cost,
                        way.reverse_cost,
                        way.oneway,
                        way.tag_id,
                        mellow.type
                    FROM chicago_ways AS way
                    LEFT JOIN mellow USING(osm_id)
                )
            """

        return f"""
            SELECT
                way.name,
                way.length_m,
                ST_AsGeoJSON(way.the_geom) AS geometry,
                mellow.type
            FROM pgr_dijkstra(
                'WITH mellow AS (
                    SELECT DISTINCT(UNNEST(ways)) AS osm_id, type
                    FROM mbm_mellowroute
                ),
                {edges_sql}
                SELECT
                    id,
                    source,
                    target,
                    CASE
                        WHEN type = ''path'' THEN cost * 0.1
                        {f"WHEN tag_id in {CYCLEWAY_TAG_IDS} THEN cost * 0.1" if enable_v2 is True else ""}
                        WHEN type = ''street'' THEN cost * 0.25
                        {f"WHEN tag_id in {RESIDENTIAL_STREET_TAG_IDS} THEN cost * 0.25" if enable_v2 is True else ""}
                        WHEN oneway = ''YES'' THEN cost * 0.5
                        WHEN tag_id in {RESIDENTIAL_STREET_TAG_IDS} THEN cost * 0.5
                        WHEN type = ''route'' THEN cost * 0.75
                        ELSE cost
                    END AS cost,
                    CASE
                        WHEN type = ''path'' THEN reverse_cost * 0.1
                        {f"WHEN tag_id in {CYCLEWAY_TAG_IDS} THEN cost * 0.1" if enable_v2 is True else ""}
                        WHEN type = ''street'' THEN reverse_cost * 0.25
                        {f"WHEN tag_id in {RESIDENTIAL_STREET_TAG_IDS} THEN cost * 0.25" if enable_v2 is True else ""}
                        WHEN oneway = ''YES'' THEN reverse_cost * 0.5
                        WHEN tag_id in {RESIDENTIAL_STREET_TAG_IDS} THEN cost * 0.5
                        WHEN type = ''route'' THEN reverse_cost * 0.75
                        ELSE reverse_cost
                    END AS reverse_cost
                FROM edge
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
        """

    def _build_bbox_query(self, source_vertex_id, target_vertex_id):
        """Get a SQL query that returns a buffered bounding box geometry
        around two points `source_vertex_id` and `target_vertex_id`.

        The size of the buffer is determined by whichever of these two values
        is smaller:

            - 1/2 the distance between source and target
            - 2 miles
        """
        assert isinstance(source_vertex_id, int)
        assert isinstance(target_vertex_id, int)

        return f"""
            -- Cast source and target vertices to IL East CRS for more
            -- precise measurements
            WITH source_vertex AS (
                SELECT id, ST_Transform(the_geom, {IL_EAST_CRS}) AS the_geom
                FROM chicago_ways_vertices_pgr
                WHERE id = {source_vertex_id}
            ),
            target_vertex AS (
                SELECT id, ST_Transform(the_geom, {IL_EAST_CRS}) AS the_geom
                FROM chicago_ways_vertices_pgr
                WHERE id = {target_vertex_id}
            ),
            combined_vertex AS (
                SELECT * FROM source_vertex
                UNION
                SELECT * FROM target_vertex
            ),
            vertex_dist AS (
                SELECT ST_Distance(source.the_geom, target.the_geom) AS ft
                FROM source_vertex AS source
                CROSS JOIN target_vertex AS target
                LIMIT 1
            )
            -- Order of PostGIS operations:
            --
            --   1. St_Collect() to gather the points into a single geometry
            --   2. ST_Envelope() to compute the bounding box around the points
            --   3. ST_Expand() to add a buffer to the bounding box
            --   4. ST_Transform() to cast back to EPSG 4326 for mapping
            SELECT
                ST_Transform(
                    ST_Expand(
                        ST_Envelope(
                            ST_Collect(vertex.the_geom)
                        ),
                        LEAST(dist.ft / 2, 2 * 5280)
                    ),
                    4326
                ) AS geom
            FROM combined_vertex AS vertex
            CROSS JOIN vertex_dist AS dist
            GROUP BY dist.ft
        """

    def _execute_bbox_query(self, source_vertex_id, target_vertex_id):
        """Get a GeoJSON feature representing the buffered bounding geometry
        around two points `source_vertex_id` and `target_vertex_id`."""
        assert isinstance(source_vertex_id, int)
        assert isinstance(target_vertex_id, int)

        route_bbox_sql = self._build_bbox_query(
            source_vertex_id,
            target_vertex_id
        )
        query_sql = f"""
            SELECT ST_AsGeoJSON(bbox.geom) AS geometry
            FROM (
                {route_bbox_sql}
            ) AS bbox
        """
        with connection.cursor() as cursor:
            cursor.execute(query_sql)
            rows = fetchall(cursor)

        if not rows or not rows[0]["geometry"]:
            raise ParseError(
                "Could not find bounding box around vertices "
                f"{source_vertex_id} and {target_vertex_id}"
            )

        bbox_geojson_str = rows[0]["geometry"]

        return {
            "type": "Feature",
            "geometry": json.loads(bbox_geojson_str),
            "properties": {
                "name": "Bounding box",
                "type": "bbox"
            }
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
