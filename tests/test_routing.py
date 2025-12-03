import pytest
from mbm.routing import _format_distance
from mbm import views


@pytest.mark.parametrize('dist_in_meters,expected', [
    (100, ('0.1 miles', '<1 minute')),
    (300, ('0.2 miles', '1 minute')),
    (1000, ('0.6 miles', '4 minutes')),
    (1609, ('1.0 miles', '6 minutes'))
])

def test_format_distance(dist_in_meters, expected):
    distance, time = _format_distance(dist_in_meters)
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
