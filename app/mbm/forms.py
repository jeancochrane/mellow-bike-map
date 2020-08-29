import json

from django import forms
from django.db import connection
from django_geomultiplechoice.widgets import GeoMultipleChoiceWidget
from leaflet.forms.widgets import LeafletWidget

from mbm.models import MellowRoute, fetchall

DEFAULT_CENTER = (41.88, -87.7)
SPATIAL_EXTENT = (-87.3, 41.5, -88, 42.15)


class MellowRouteMultipleChoiceWidget(GeoMultipleChoiceWidget):
    def get_features(self):
        return [
            {
                'type': 'Feature',
                'geometry': json.loads(choice['geom']),
                'properties': {
                    'id': choice_id,
                }
            }
            for choice_id, choice in self.choices
        ]


class MellowRouteCreateForm(forms.ModelForm):
    class Meta:
        model = MellowRoute
        fields = ['name', 'slug', 'bounding_box']
        widgets = {
            'bounding_box': LeafletWidget(attrs={
                'map_height': '500px',
                'map_width': '100%',
                'display_raw': True,
                'settings_overrides': {
                    'DEFAULT_ZOOM': 13,
                    'DEFAULT_CENTER': DEFAULT_CENTER,
                    'SPATIAL_EXTENT': SPATIAL_EXTENT,
                },
            })
        }

    def save(self):
        # Create instances for all three route types
        street_instance = super().save()

        # Copy the instance by setting its pk to None
        # See: https://docs.djangoproject.com/en/3.1/topics/db/queries/#copying-model-instances
        route_instance = street_instance
        route_instance.pk = None
        route_instance.type = MellowRoute.Type.ROUTE
        route_instance.save()

        path_instance = route_instance
        path_instance.pk = None
        path_instance.type = MellowRoute.Type.PATH
        path_instance.save()

        return path_instance


class MellowRouteNeighborhoodEditForm(forms.ModelForm):
    class Meta:
        model = MellowRoute
        fields = ['name', 'slug', 'bounding_box']
        widgets = {
            'bounding_box': LeafletWidget(attrs={
                'map_height': '500px',
                'map_width': '100%',
                'display_raw': True,
            })
        }


class MellowRouteEditForm(forms.ModelForm):
    class Meta:
        model = MellowRoute
        fields = ['name', 'slug', 'type', 'ways']
        widgets = {
            'name': forms.TextInput(attrs={'readonly': True}),
            'slug': forms.TextInput(attrs={'readonly': True}),
            'type': forms.TextInput(attrs={'readonly': True})
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        bounding_box = self.instance.bounding_box
        if bounding_box is not None:
            # These coords are flipped for some reason (lng, lat)
            bounding_box_centroid = (
                bounding_box.centroid.coords[1],
                bounding_box.centroid.coords[0],
            )
            # Retrieve ways with raw query for speed
            way_query = """
                SELECT
                    osm_id::varchar AS id,
                    ST_AsGeoJSON(ST_Union(the_geom)) AS geom
                FROM chicago_ways
                WHERE the_geom && (
                    SELECT bounding_box
                    FROM mbm_mellowroute
                    WHERE slug = %s
                    AND type = %s
                )
                GROUP BY osm_id
            """
            way_query_params = [self.instance.slug, self.instance.type]
        else:
            bounding_box_centroid = DEFAULT_CENTER
            way_query = """
                SELECT
                    osm_id::varchar AS id,
                    ST_AsGeoJSON(ST_Union(the_geom)) AS geom
                FROM chicago_ways
                WHERE the_geom && ST_MakeEnvelope(%s, %s, %s, %s)
                GROUP BY osm_id
            """
            way_query_params = SPATIAL_EXTENT

        with connection.cursor() as cursor:
            cursor.execute(way_query, way_query_params)
            choices = fetchall(cursor)

        self.fields['ways'].widget = MellowRouteMultipleChoiceWidget(
            choices=[(choice['id'], choice) for choice in choices],
            settings_overrides={
                'DEFAULT_ZOOM': 13,
                'DEFAULT_CENTER': bounding_box_centroid,
                'MAP_HEIGHT': '500px',
                'MAP_WIDTH': '100%',
                'MAP_LAYER_STYLE': {
                    'color': '#7a7a7a',
                    'weight': 3,
                    'opacity': 0.5,
                    'fillColor': '#999999',
                    'fillOpacity': 0.3,
                },
                'MAP_LAYER_SELECTED_STYLE': {
                    'color': 'black',
                    'weight': 3,
                    'opacity': 1,
                    'fillColor': 'black',
                    'fillOpacity': 0.7
                }
            }
        )
