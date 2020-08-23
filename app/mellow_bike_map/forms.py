import json

from django import forms
from django.db import connection
from django_geomultiplechoice.widgets import GeoMultipleChoiceWidget
from mellow_bike_map.models import MellowWay, fetchall


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


class MellowWayForm(forms.ModelForm):
    class Meta:
        model = MellowWay
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        with connection.cursor() as cursor:
            # Use raw query for speed
            # TODO: Cut up by neighborhood instead of just restricting to Edgewater
            cursor.execute("""
                SELECT
                    osm_id::varchar AS id,
                    ST_AsGeoJSON(ST_Union(the_geom)) AS geom
                FROM chicago_ways
                WHERE the_geom && ST_MakeEnvelope(-87.6888, 41.9754, -87.6421, 41.9944)
                GROUP BY osm_id
            """)
            choices = fetchall(cursor)

        self.fields['ways'].widget = MellowWayMultipleChoiceWidget(
            choices=[(choice['id'], choice) for choice in choices],
            settings_overrides={
                'DEFAULT_ZOOM': 12,
                'DEFAULT_CENTER': (41.88, -87.7),
                'SPATIAL_EXTENT': (-87.3, 41.5, -88, 42.15),
                'MAP_HEIGHT': '400px',
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
