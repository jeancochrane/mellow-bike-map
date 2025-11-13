import pytest
from mbm.routing import _format_distance


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