import json

from django import forms
from django.db import connection
from django_geomultiplechoice.widgets import GeoMultipleChoiceWidget
from leaflet.forms.widgets import LeafletWidget

from mellow_bike_map.models import MellowWay, fetchall

DEFAULT_CENTER = (41.88, -87.7)
SPATIAL_EXTENT = (-87.3, 41.5, -88, 42.15)


class MellowWayMultipleChoiceWidget(GeoMultipleChoiceWidget):
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


class MellowWayCreateForm(forms.ModelForm):
    class Meta:
        model = MellowWay
        fields = ['name', 'slug', 'bounding_box']
        widgets = {
            'bounding_box': LeafletWidget(attrs={
                'settings_overrides': {
                    'MAP_HEIGHT': '500px',
                    'MAP_WIDTH': '100%',
                    'DEFAULT_ZOOM': 13,
                    'DEFAULT_CENTER': DEFAULT_CENTER,
                    'SPATIAL_EXTENT': SPATIAL_EXTENT,
                }
            })
        }


class MellowWayEditForm(forms.ModelForm):
    class Meta:
        model = MellowWay
        fields = ['name', 'slug', 'bounding_box', 'ways']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        bounding_box = self.instance.bounding_box
        if bounding_box is not None:
            bounding_box_centroid = bounding_box.centroid.coords
            bounding_box_coords = bounding_box.coords[0]
            top_left, bottom_right = bounding_box_coords[0], bounding_box_coords[2]
            x1, y1 = top_left[0], top_left[1]
            x2, y2 = bottom_right[0], bottom_right[1]
            bounding_box_extent = (x1, y1, x2, y2)
        else:
            bounding_box_centroid = DEFAULT_CENTER
            bounding_box_extent = SPATIAL_EXTENT

        self.fields['bounding_box'].widget = LeafletWidget(attrs={
            'settings_overrides': {
                'MAP_HEIGHT': '500px',
                'MAP_WIDTH': '100%',
                'DEFAULT_ZOOM': 13,
                'DEFAULT_CENTER': bounding_box_centroid,
                'SPATIAL_EXTENT': bounding_box_extent,
            }
        })

        with connection.cursor() as cursor:
            # Use raw query for speed
            cursor.execute("""
                SELECT
                    osm_id::varchar AS id,
                    ST_AsGeoJSON(ST_Union(the_geom)) AS geom
                FROM chicago_ways
                WHERE the_geom && ST_MakeEnvelope(%s, %s, %s, %s)
                GROUP BY osm_id
            """, bounding_box_extent)
            choices = fetchall(cursor)

        self.fields['ways'].widget = MellowWayMultipleChoiceWidget(
            choices=[(choice['id'], choice) for choice in choices],
            settings_overrides={
                'DEFAULT_ZOOM': 13,
                'DEFAULT_CENTER': bounding_box_centroid,
                'SPATIAL_EXTENT': bounding_box_extent,
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
