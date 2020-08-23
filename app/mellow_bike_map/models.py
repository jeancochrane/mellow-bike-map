from django.db import models
from django.contrib.postgres import fields as pg_models
from django.contrib.gis.db import models as gis_models


class Edge(models.Model):
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


class MellowWay(models.Model):
    slug = models.SlugField(max_length=50, primary_key=True)
    name = models.CharField(max_length=150)
    ways = pg_models.ArrayField(
        models.BigIntegerField(),
        help_text=(
            'Select one or more streets on the map to mark them as mellow. '
            'Add or remove a street by clicking on it, or remove all streets '
            'by clicking the "Clear all" button.'
        )
    )


def fetchall(cursor):
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]
