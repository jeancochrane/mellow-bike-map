import pytest
from mbm import views


@pytest.mark.parametrize('dist_in_meters,expected', [
    (100, ('0.1 miles', '<1 minute')),
    (215, ('0.1 miles', '1 minute')),
    (1000, ('0.6 miles', '5 minutes')),
    (1609, ('1.0 miles', '7 minutes'))
])
def test_format_distance(dist_in_meters, expected):
    route = views.Route()
    distance, time = route.format_distance(dist_in_meters)
    expected_dist, expected_time = expected
    assert distance == expected_dist
    assert time == expected_time
