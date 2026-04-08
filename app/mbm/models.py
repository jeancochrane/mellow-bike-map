import json

from django.db import models, connection
from django.contrib.postgres import fields as pg_models
from django.contrib.gis.db import models as gis_models


class Edge(models.Model):
    """
    Unmanaged model corresponding to an edge stored in the edgelist. Edges are
    what we use to calculate routes, and are comprised of segments of OSM Ways
    that have been split at nodes and intersections.

    The underlying table in the database is the `clean_ways` materialized view,
    which takes a set of edges produced by an osm2pgrouting call and filters
    them to remove unimportant sidewalks. The data flow looks like this:

    `osm_ways`: Raw OSM way table from an Overpass API mirror
    |
    --> `chicago_ways`: Intermediate way table, transformed for bike routing
         |
         --> `clean_ways`: Materialized view that drops unimportant sidewalks

    See the Makefile for more details about `osm_ways` and `chicago_ways`.
    See the `0004_add_clean_ways_view` migration for the `clean_ways` view
    definition.

    We use a materialized view to filter out sidewalks so that we can
    preserve those sidewalks in the underlying `chicago_ways` table. That
    makes it easy to tweak the set of important sidewalks if our needs change in
    the future, because the `chicago_ways` table is the source of the ways
    data that powers the admin tagging interface. Hence, we can tag the most
    important sidewalks, filter out the rest from the routing interface, and
    still retain the ability to retag important sidewalks and quickly refresh
    the relation that powers our routing algorithm.
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
        db_table = 'clean_ways'


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
        SIDEWALK = ('sidewalk', 'Connecting sidewalk')

    slug = models.SlugField(max_length=50)
    name = models.CharField(max_length=150)
    bounding_box = gis_models.PolygonField(null=True, blank=True)
    type = models.CharField(max_length=8, choices=Type.choices, default=Type.STREET)
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
    def all(cls, exclude_sidewalks=False):
        """
        Retrieve all mellow routes and return their unioned geometries as a
        dictionary grouped by route type.

        If exclude_sidewalks is True, skip mellow routes that are sidewalks.
        This is useful because sidewalk geometries tend to look weird.
        """
        base_query = """
            SELECT
                routes.type,
                ST_AsGeoJSON(ST_Union(clean_ways.the_geom)) AS geometry
            FROM clean_ways
            JOIN (
                SELECT UNNEST(ways) AS osm_id, type
                FROM mbm_mellowroute
                {subquery_where}
            ) as routes
            USING(osm_id)
            GROUP BY routes.type
        """

        params = []
        subquery_where = ""
        if exclude_sidewalks:
            subquery_where = "WHERE type != %s"
            params.append('sidewalk')

        # Compose the final query with the correct subquery WHERE clause
        final_query = base_query.format(subquery_where=subquery_where)

        with connection.cursor() as cursor:
            cursor.execute(final_query, params)
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


def fetchall(cursor):
    """
    Convenience function for fetching rows from a psycopg2 cursor as
    Python dictionaries.
    """
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]
