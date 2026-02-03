import json

from django.db import models, connection
from django.contrib.postgres import fields as pg_models
from django.contrib.gis.db import models as gis_models


class Edge(models.Model):
    """
    Unmanaged model corresponding to an edge stored in the edgelist. Edges are
    what we use to calculate routes, and are comprised of segments of OSM Ways
    that have been split at nodes and intersections.
    """
    gid = models.BigIntegerField(primary_key=True)
    osm_id = models.BigIntegerField()
    tag_id = models.IntegerField()
    length = models.FloatField()
    length_m = models.FloatField()
    name = models.TextField()
    source = models.BigIntegerField()
    target = models.BigIntegerField()
    source_osm = models.BigIntegerField()
    target_osm = models.BigIntegerField()
    cost = models.FloatField()
    reverse_cost = models.FloatField()
    cost_s = models.FloatField()
    reverse_cost_s = models.FloatField()
    rule = models.TextField()
    one_way = models.IntegerField()
    oneway = models.TextField()
    x1 = models.FloatField()
    y1 = models.FloatField()
    x2 = models.FloatField()
    y2 = models.FloatField()
    maxspeed_forward = models.FloatField()
    maxspeed_backward = models.FloatField()
    priority = models.FloatField()
    the_geom = gis_models.LineStringField()

    class Meta:
        managed = False
        db_table = 'chicago_ways'


class Way(models.Model):
    """
    Unmanaged model corresponding to an OSM Way in the database. OSM Ways are
    split up at intersections to become Edges.
    """
    osm_id = models.BigIntegerField(primary_key=True)
    members = pg_models.HStoreField()
    tags = pg_models.HStoreField()
    tag_name = models.TextField()
    tag_value = models.TextField()
    name = models.TextField()
    the_geom = gis_models.LineStringField()

    class Meta:
        managed = False
        db_table = 'osm_ways'


class MellowRoute(models.Model):
    """
    Model representing a collection of mellow routes, bounded by a particular
    bounding_box. Each instance of this model represents a "neighborhood" and
    the mellow routes within that neighborhood.
    """
    class Type(models.TextChoices):
        ROUTE = ('route', 'Official bike route')
        STREET = ('street', 'Mellow street')
        PATH = ('path', 'Off-street bike path')

    slug = models.SlugField(max_length=50)
    name = models.CharField(max_length=150)
    bounding_box = gis_models.PolygonField(null=True, blank=True)
    type = models.CharField(max_length=6, choices=Type.choices, default=Type.STREET)
    ways = pg_models.ArrayField(
        models.BigIntegerField(),
        help_text=(
            'Select one or more streets on the map to mark them as mellow. '
            'Add or remove a street by clicking on it, or remove all streets '
            'by clicking the "Clear all" button.'
        ),
        default=list
    )

    class Meta:
        unique_together = ('slug', 'type')

    @classmethod
    def all(cls):
        """
        Retrieve all mellow routes and return their unioned geometries as a
        dictionary grouped by route type.
        """
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    routes.type,
                    ST_AsGeoJSON(ST_Union(chicago_ways.the_geom)) AS geometry
                FROM chicago_ways
                JOIN (
                    SELECT UNNEST(ways) AS osm_id, type
                    FROM mbm_mellowroute
                ) as routes
                USING(osm_id)
                GROUP BY routes.type
            """)
            rows = fetchall(cursor)

        return {
            'type': 'FeatureCollection',
            'features': [
                {
                    'type': 'Feature',
                    'geometry': json.loads(row['geometry']),
                    'properties': {'type': row['type']}
                }
                for row in rows
            ]
        }

    @classmethod
    def all_graph_components(cls):
        """
        Retrieve all ways grouped by connected component, for debugging.
        """
        with connection.cursor() as cursor:
            cursor.execute("""
                WITH components AS (
                    SELECT * FROM pgr_connectedComponents(
                        'SELECT gid AS id, source, target, cost, reverse_cost FROM chicago_ways'
                    )
                ),
                edges_with_component AS (
                    SELECT way.gid, way.the_geom, components.component
                    FROM chicago_ways AS way
                    JOIN components
                    ON components.node = way.source
                ),
                component_sizes AS (
                    SELECT component, COUNT(*) AS edge_count
                    FROM edges_with_component
                    GROUP BY component
                ),
                largest_component AS (
                    SELECT component
                    FROM component_sizes
                    ORDER BY edge_count DESC
                    LIMIT 1
                )
                SELECT
                    component,
                    ST_AsGeoJSON(ST_Collect(the_geom)) AS geometry
                FROM edges_with_component
                WHERE component NOT IN (SELECT component FROM largest_component)
                GROUP BY component
                ORDER BY component
            """)
            rows = fetchall(cursor)

        return {
            'type': 'FeatureCollection',
            'features': [
                {
                    'type': 'Feature',
                    'geometry': json.loads(row['geometry']),
                    'properties': {'component': row['component']}
                }
                for row in rows
            ]
        }

def fetchall(cursor):
    """
    Convenience function for fetching rows from a psycopg2 cursor as
    Python dictionaries.
    """
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]
