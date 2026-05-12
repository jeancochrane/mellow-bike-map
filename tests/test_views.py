import pytest
from unittest.mock import patch, call
from mbm import views


@pytest.mark.parametrize('dist_in_meters,expected', [
    (100, ('0.1 miles', '<1 minute')),
    (300, ('0.2 miles', '1 minute')),
    (1000, ('0.6 miles', '4 minutes')),
    (1609, ('1.0 miles', '6 minutes'))
])
def test_format_distance(dist_in_meters, expected):
    route = views.Route()
    distance, time = route.format_distance(dist_in_meters)
    expected_dist, expected_time = expected
    assert distance == expected_dist
    assert time == expected_time

def test_get_major_streets_returns_major_streets():
    route = views.Route()
    rows = [
        {'name': 'Street A', 'length_m': 600},
        {'name': 'Street B', 'length_m': 400},
        {'name': 'Street C', 'length_m': 200},
        {'name': 'Street D', 'length_m': 150},
        {'name': None, 'length_m': 250},
    ]
    total_length = sum(row['length_m'] for row in rows)
    assert route.get_major_streets(rows, total_length) == ['Street A', 'Street B']

def test_get_major_streets_returns_at_most_three_streets_sorted_alphabetically_if_a_tie_occurs():
    route = views.Route()
    rows = [
        {'name': 'Street A', 'length_m': 50},
        {'name': 'Street B', 'length_m': 50},
        {'name': 'Street D', 'length_m': 50},
        {'name': 'Street C', 'length_m': 50},
    ]
    total_length = sum(row['length_m'] for row in rows)
    assert route.get_major_streets(rows, total_length) == ['Street A', 'Street B', 'Street C']

def test_get_major_streets_returns_empty_when_no_major_streets():
    route = views.Route()
    rows = [
        {'name': 'Street A', 'length_m': 50},
        {'name': 'Street B', 'length_m': 50},
        {'name': 'Street C', 'length_m': 50},
        {'name': 'Street D', 'length_m': 50},
        {'name': 'Street E', 'length_m': 50},
        {'name': 'Street F', 'length_m': 50},
    ]
    total_length = sum(row['length_m'] for row in rows)
    assert route.get_major_streets(rows, total_length) == []

def test_get_major_streets_does_not_return_unnamed_streets():
    route = views.Route()
    rows = [
        {'name': 'Short Street', 'length_m': 100},
        {'name': 'Long Street', 'length_m': 100},
        {'name': None, 'length_m': 1000},
    ]
    total_length = sum(row['length_m'] for row in rows)
    assert route.get_major_streets(rows, total_length) == []


def test_build_route_query_with_bbox_includes_bbox_cte():
    route = views.Route()
    sql = route._build_route_query(1, 2, use_bbox=True)
    assert 'bbox AS' in sql
    assert 'JOIN bbox ON' in sql


def test_build_route_query_without_bbox_excludes_bbox_cte():
    route = views.Route()
    sql = route._build_route_query(1, 2, use_bbox=False)
    assert 'bbox AS' not in sql
    assert 'JOIN bbox ON' not in sql


def test_build_route_query_without_bbox_queries_all_ways():
    route = views.Route()
    sql = route._build_route_query(1, 2, use_bbox=False)
    assert 'LEFT JOIN mellow USING(osm_id)' in sql


def test_build_route_query_both_modes_include_cost_logic():
    route = views.Route()
    for use_bbox in (True, False):
        sql = route._build_route_query(1, 2, use_bbox=use_bbox)
        assert 'pgr_dijkstra' in sql
        assert 'reverse_cost' in sql


# Fixture representing a dummy row that the routing algorithm might return as
# part of a route
STUB_ROWS = [
    {'name': 'Main St', 'length_m': 500, 'geometry': '{"type":"LineString","coordinates":[]}', 'type': 'street'}
]


def test_get_route_uses_bbox_when_route_found():
    route = views.Route()
    with patch.object(route, '_execute_route_query', return_value=STUB_ROWS) as mock_exec, \
         patch.object(route, '_execute_bbox_query', return_value={}):
        result = route.get_route(1, 2)

    mock_exec.assert_called_once_with(1, 2, use_bbox=True)
    assert result['properties'].get('used_bbox') is None  # not set when show_bbox=False


def test_get_route_falls_back_when_bbox_returns_no_rows():
    route = views.Route()
    side_effects = [[], STUB_ROWS]
    with patch.object(route, '_execute_route_query', side_effect=side_effects) as mock_exec:
        result = route.get_route(1, 2)

    assert mock_exec.call_count == 2
    assert mock_exec.call_args_list == [
        call(1, 2, use_bbox=True),
        call(1, 2, use_bbox=False),
    ]
    assert len(result['features']) == 1


def test_get_route_show_bbox_true_used_bbox_true_when_route_found_in_bbox():
    route = views.Route()
    bbox_feature = {'type': 'Feature', 'geometry': {}, 'properties': {'type': 'bbox'}}
    with patch.object(route, '_execute_route_query', return_value=STUB_ROWS), \
         patch.object(route, '_execute_bbox_query', return_value=bbox_feature):
        result = route.get_route(1, 2, show_bbox=True)

    assert result['properties']['used_bbox'] is True
    assert bbox_feature in result['features']


def test_get_route_show_bbox_true_used_bbox_false_when_fallback_fires():
    route = views.Route()
    with patch.object(route, '_execute_route_query', side_effect=[[], STUB_ROWS]), \
         patch.object(route, '_execute_bbox_query') as mock_bbox_feature:
        result = route.get_route(1, 2, show_bbox=True)

    assert result['properties']['used_bbox'] is False
    mock_bbox_feature.assert_not_called()
    assert not any(f.get('properties', {}).get('type') == 'bbox' for f in result['features'])

