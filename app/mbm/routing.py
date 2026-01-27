from typing import List, Tuple
import json
from django.db import connection
from mbm.models import fetchall
from mbm.types import Route

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

def calculate_route(source_vertex_id: int, target_vertex_id: int, enable_v2: bool = False) -> Tuple[Route, str, str]:
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

    features: Route = [
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

    dist_in_meters = sum(row['length_m'] for row in rows)
    return features, *_format_distance(dist_in_meters)


def _format_distance(dist_in_meters: float) -> Tuple[str, str]:
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