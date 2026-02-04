from typing import List

import pytest
from mbm.directions import (
    Direction,
    directions_list,
    _describe_unnamed_street,
    _format_distance,
    _heading_to_english_maneuver,
    _should_merge_segments,
    _merge_with_previous_direction,
)


class TestHeadingToEnglishManeuver:
    def test_no_previous_heading_returns_continue_with_cardinal(self):
        result = _heading_to_english_maneuver(heading=90.0, previous_heading=None)
        assert result == {'maneuver': 'Continue', 'cardinal': 'east'}

    def test_slight_right_when_heading_changes_small_amount(self):
        result = _heading_to_english_maneuver(heading=30.0, previous_heading=0.0)
        assert result['maneuver'] == 'Turn slightly to the right'
        assert result['cardinal'] == 'northeast'

    def test_cardinal_rounds_to_nearest_direction(self):
        result = _heading_to_english_maneuver(heading=268.0, previous_heading=180.0)
        assert result['cardinal'] == 'west'

    def test_wraparound_angle_keeps_continue(self):
        result = _heading_to_english_maneuver(heading=10.0, previous_heading=350.0)
        assert result['maneuver'] == 'Continue'
        assert result['cardinal'] == 'north'


class TestDescribeUnnamedStreet:
    @pytest.mark.parametrize('osm_tags,park_name,expected', [
        (None, None, 'an unknown street'),
        ('not-a-dict', None, 'an unknown street'),
        ({'highway': 'service', 'service': 'alley'}, None, 'an alley'),
        ({'highway': 'service'}, None, 'an access road'),
        ({'footway': 'crossing'}, None, 'a crosswalk'),
        ({'highway': 'cycleway'}, None, 'a bike path'),
        ({'bicycle': 'designated'}, None, 'a bike path'),
        ({'highway': 'pedestrian'}, None, 'a pedestrian path'),
        ({'highway': 'footway'}, None, 'a sidewalk'),
        ({'footway': 'sidewalk'}, None, 'a sidewalk'),
        ({'highway': 'path', 'bicycle': 'permissive'}, None, 'a mixed-use path'),
        ({'highway': 'residential'}, 'Lincoln Park', 'a path inside Lincoln Park'),
        ({'highway': 'cycleway'}, 'Grant Park', 'a bike path inside Grant Park'),
    ])
    def test_describes_unnamed_street(self, osm_tags, park_name, expected):
        assert _describe_unnamed_street(osm_tags, park_name) == expected


class TestDirectionsFormatDistance:
    @pytest.mark.parametrize('meters,expected', [
        (0.3048, '1 foot'),
        (0.6096, '2 feet'),
        (100.0, '328 feet'),
        (160.9344, '0.1 miles'),
        (1609.344, '1.0 mile'),
        (1.05 * 1609.344, '1.1 miles'),
    ])
    def test_format_distance(self, meters, expected):
        assert _format_distance(meters) == expected


class TestShouldMergeSegments:
    def test_slight_turn_same_named_street_should_merge(self):
        result = _should_merge_segments(
            maneuver='Turn slightly to the right',
            new_segment_effective_name='Main Street',
            previous_segment_effective_name='Main Street',
            name='Main Street'
        )
        assert result is True
    
    def test_slight_turn_left_same_named_street_should_merge(self):
        result = _should_merge_segments(
            maneuver='Turn slightly to the left',
            new_segment_effective_name='Oak Avenue',
            previous_segment_effective_name='Oak Avenue',
            name='Oak Avenue'
        )
        assert result is True
    
    def test_slight_turn_different_named_street_should_not_merge(self):
        result = _should_merge_segments(
            maneuver='Turn slightly to the right',
            new_segment_effective_name='Main Street',
            previous_segment_effective_name='Oak Avenue',
            name='Main Street'
        )
        assert result is False
    
    def test_slight_turn_unnamed_street_should_not_merge(self):
        result = _should_merge_segments(
            maneuver='Turn slightly to the right',
            new_segment_effective_name='an unknown street',
            previous_segment_effective_name='an unknown street',
            name=None
        )
        assert result is False
    
    def test_continue_same_street_should_merge(self):
        result = _should_merge_segments(
            maneuver='Continue',
            new_segment_effective_name='Main Street',
            previous_segment_effective_name='Main Street',
            name='Main Street'
        )
        assert result is True
    
    def test_continue_different_street_should_not_merge(self):
        result = _should_merge_segments(
            maneuver='Continue',
            new_segment_effective_name='Main Street',
            previous_segment_effective_name='Oak Avenue',
            name='Main Street'
        )
        assert result is False
    
    def test_turn_right_should_not_merge(self):
        result = _should_merge_segments(
            maneuver='Turn right',
            new_segment_effective_name='Main Street',
            previous_segment_effective_name='Main Street',
            name='Main Street'
        )
        assert result is False
    
    def test_turn_left_should_not_merge(self):
        result = _should_merge_segments(
            maneuver='Turn left',
            new_segment_effective_name='Main Street',
            previous_segment_effective_name='Main Street',
            name='Main Street'
        )
        assert result is False
    
    def test_sharp_turn_should_not_merge(self):
        result = _should_merge_segments(
            maneuver='Take a sharp right turn',
            new_segment_effective_name='Main Street',
            previous_segment_effective_name='Main Street',
            name='Main Street'
        )
        assert result is False
    
    def test_turn_around_should_not_merge(self):
        result = _should_merge_segments(
            maneuver='Turn around',
            new_segment_effective_name='Main Street',
            previous_segment_effective_name='Main Street',
            name='Main Street'
        )
        assert result is False
    
    def test_street_name_changed_should_not_merge(self):
        result = _should_merge_segments(
            maneuver='Continue',
            new_segment_effective_name='Oak Avenue',
            previous_segment_effective_name='Main Street',
            name='Oak Avenue'
        )
        assert result is False
    
    def test_first_segment_no_previous_heading_should_not_merge(self):
        result = _should_merge_segments(
            maneuver='Continue',
            new_segment_effective_name='Main Street',
            previous_segment_effective_name=None,
            name='Main Street'
        )
        assert result is False
    
    def test_slight_turn_same_unnamed_street_should_not_merge(self):
        result = _should_merge_segments(
            maneuver='Turn slightly to the right',
            new_segment_effective_name='an unknown street',
            previous_segment_effective_name='an unknown street',
            name=None
        )
        assert result is False
    
    def test_slight_turn_different_unnamed_streets_should_not_merge(self):
        result = _should_merge_segments(
            maneuver='Turn slightly to the right',
            new_segment_effective_name='an unknown street',
            previous_segment_effective_name='an alley',
            name=None
        )
        assert result is False
    
    def test_continue_unnamed_street_same_should_merge(self):
        result = _should_merge_segments(
            maneuver='Continue',
            new_segment_effective_name='an unknown street',
            previous_segment_effective_name='an unknown street',
            name=None
        )
        assert result is True
    
    def test_slight_turn_first_segment_should_not_merge(self):
        result = _should_merge_segments(
            maneuver='Turn slightly to the right',
            new_segment_effective_name='Main Street',
            previous_segment_effective_name=None,
            name='Main Street'
        )
        assert result is False


class TestMergeWithPreviousDirection:
    def test_basic_merge(self):
        directions = [{
            'name': 'Main Street',
            'effectiveName': 'Main Street',
            'distance': 100.0,
            'maneuver': 'Continue',
            'heading': 0.0,
            'cardinal': 'north',
            'type': 'route',
            'osmData': {'osm_id': 1, 'tag_id': 2},
            'directionSegments': [{
                'gid': 101,
                'osmData': {'osm_id': 1, 'tag_id': 2},
                'maneuver': 'Continue',
                'cardinal': 'north',
                'distance': 100.0,
                'name': 'Main Street',
                'effectiveName': 'Main Street',
                'featureIndex': 0,
            }],
            'featureIndices': [0],
        }]

        direction_segment = {
            'gid': 1,
            'osmData': {'osm_id': 3, 'tag_id': 4},
            'maneuver': 'Continue',
            'cardinal': 'north',
            'distance': 50.0,
            'name': 'Main Street',
            'effectiveName': 'Main Street',
            'featureIndex': 1,
        }

        _merge_with_previous_direction(directions, direction_segment)

        assert directions[0]['distance'] == 150.0
        assert len(directions[0]['directionSegments']) == 2
        assert directions[0]['directionSegments'][1] == direction_segment
        assert len(directions[0]['featureIndices']) == 2
        assert directions[0]['featureIndices'][1] == 1

    def test_empty_directions_list(self):
        directions: List[Direction] = []

        direction_segment = {
            'gid': 2,
            'osmData': {'osm_id': 1},
            'maneuver': 'Continue',
            'cardinal': 'north',
            'distance': 50.0,
            'name': 'Main Street',
            'effectiveName': 'Main Street',
            'featureIndex': 0,
        }

        _merge_with_previous_direction(directions, direction_segment)

        assert directions == []

    def test_name_backfill(self):
        directions = [{
            'name': None,
            'effectiveName': 'an unknown street',
            'distance': 100.0,
            'maneuver': 'Continue',
            'heading': 0.0,
            'cardinal': 'north',
            'type': 'route',
            'osmData': {'osm_id': 1},
            'directionSegments': [{
                'gid': 102,
                'osmData': {'osm_id': 1},
                'maneuver': 'Continue',
                'cardinal': 'north',
                'distance': 100.0,
                'name': None,
                'effectiveName': 'an unknown street',
                'featureIndex': 0,
            }],
            'featureIndices': [0],
        }]

        direction_segment = {
            'gid': 3,
            'osmData': {'osm_id': 2},
            'maneuver': 'Continue',
            'cardinal': 'north',
            'distance': 50.0,
            'name': 'Main Street',
            'effectiveName': 'Main Street',
            'featureIndex': 1,
        }

        _merge_with_previous_direction(directions, direction_segment)

        assert directions[0]['name'] == 'Main Street'
        assert directions[0]['effectiveName'] == 'Main Street'

    def test_osm_data_preservation(self):
        directions = [{
            'name': None,
            'effectiveName': 'an unknown street',
            'distance': 100.0,
            'maneuver': 'Continue',
            'heading': 0.0,
            'cardinal': 'north',
            'type': 'route',
            'osmData': None,
            'directionSegments': [{
                'gid': 103,
                'osmData': None,
                'maneuver': 'Continue',
                'cardinal': 'north',
                'distance': 100.0,
                'name': None,
                'effectiveName': 'an unknown street',
                'featureIndex': 0,
            }],
            'featureIndices': [0],
        }]

        direction_segment = {
            'gid': 4,
            'osmData': {'osm_id': 2, 'osm_tags': {'highway': 'service'}},
            'maneuver': 'Continue',
            'cardinal': 'north',
            'distance': 50.0,
            'name': None,
            'effectiveName': 'an access road',
            'featureIndex': 1,
        }

        _merge_with_previous_direction(directions, direction_segment)

        assert directions[0]['osmData'] == {'osm_id': 2, 'osm_tags': {'highway': 'service'}}
        assert directions[0]['effectiveName'] == 'an access road'

    def test_multiple_merges(self):
        directions = [{
            'name': 'Main Street',
            'effectiveName': 'Main Street',
            'distance': 100.0,
            'maneuver': 'Continue',
            'heading': 0.0,
            'cardinal': 'north',
            'type': 'route',
            'osmData': {'osm_id': 1},
            'directionSegments': [{
                'gid': 104,
                'osmData': {'osm_id': 1},
                'maneuver': 'Continue',
                'cardinal': 'north',
                'distance': 100.0,
                'name': 'Main Street',
                'effectiveName': 'Main Street',
                'featureIndex': 0,
            }],
            'featureIndices': [0],
        }]

        direction_segment_1 = {
            'gid': 5,
            'osmData': {'osm_id': 2},
            'maneuver': 'Continue',
            'cardinal': 'north',
            'distance': 50.0,
            'name': 'Main Street',
            'effectiveName': 'Main Street',
            'featureIndex': 1,
        }
        direction_segment_2 = {
            'gid': 6,
            'osmData': {'osm_id': 3},
            'maneuver': 'Continue',
            'cardinal': 'north',
            'distance': 75.0,
            'name': 'Main Street',
            'effectiveName': 'Main Street',
            'featureIndex': 2,
        }

        _merge_with_previous_direction(directions, direction_segment_1)
        _merge_with_previous_direction(directions, direction_segment_2)

        assert directions[0]['distance'] == 225.0
        assert len(directions[0]['directionSegments']) == 3
        assert len(directions[0]['featureIndices']) == 3
        assert directions[0]['featureIndices'] == [0, 1, 2]

    def test_no_name_backfill_when_previous_has_name(self):
        directions = [{
            'name': 'Main Street',
            'effectiveName': 'Main Street',
            'distance': 100.0,
            'maneuver': 'Continue',
            'heading': 0.0,
            'cardinal': 'north',
            'type': 'route',
            'osmData': {'osm_id': 1},
            'directionSegments': [{
                'gid': 105,
                'osmData': {'osm_id': 1},
                'maneuver': 'Continue',
                'cardinal': 'north',
                'distance': 100.0,
                'name': 'Main Street',
                'effectiveName': 'Main Street',
                'featureIndex': 0,
            }],
            'featureIndices': [0],
        }]

        direction_segment = {
            'gid': 7,
            'osmData': {'osm_id': 2},
            'maneuver': 'Continue',
            'cardinal': 'north',
            'distance': 50.0,
            'name': 'Oak Avenue',
            'effectiveName': 'Oak Avenue',
            'featureIndex': 1,
        }

        _merge_with_previous_direction(directions, direction_segment)

        assert directions[0]['name'] == 'Main Street'
        assert directions[0]['effectiveName'] == 'Main Street'

    def test_no_osm_data_update_when_previous_has_name(self):
        directions = [{
            'name': 'Main Street',
            'effectiveName': 'Main Street',
            'distance': 100.0,
            'maneuver': 'Continue',
            'heading': 0.0,
            'cardinal': 'north',
            'type': 'route',
            'osmData': {'osm_id': 1},
            'directionSegments': [{
                'gid': 106,
                'osmData': {'osm_id': 1},
                'maneuver': 'Continue',
                'cardinal': 'north',
                'distance': 100.0,
                'name': 'Main Street',
                'effectiveName': 'Main Street',
                'featureIndex': 0,
            }],
            'featureIndices': [0],
        }]

        direction_segment = {
            'gid': 8,
            'osmData': {'osm_id': 2, 'osm_tags': {'highway': 'service'}},
            'maneuver': 'Continue',
            'cardinal': 'north',
            'distance': 50.0,
            'name': None,
            'effectiveName': 'an access road',
            'featureIndex': 1,
        }
        original_osm_data = directions[0]['osmData'].copy()

        _merge_with_previous_direction(directions, direction_segment)

        assert directions[0]['osmData'] == original_osm_data
        assert directions[0]['effectiveName'] == 'Main Street'


class TestDirectionsList:
    def test_directions_list(self):
        features = [
            {
                'type': 'Feature',
                'geometry': {},
                'properties': {
                    'name': 'Main Street',
                    'type': 'route',
                    'distance': 100.0,
                    'heading': 0.0,
                    'gid': 11,
                },
            },
            {
                'type': 'Feature',
                'geometry': {},
                'properties': {
                    'name': 'Main Street',
                    'type': 'route',
                    'distance': 200.0,
                    'heading': 30.0,
                    'gid': 12,
                },
            },
            {
                'type': 'Feature',
                'geometry': {},
                'properties': {
                    'name': 'Oak Avenue',
                    'type': 'route',
                    'distance': 50.0,
                    'heading': 90.0,
                    'gid': 13,
                },
            },
            {
                'type': 'Feature',
                'geometry': {},
                'properties': {
                    'name': 'Oak Avenue',
                    'type': 'route',
                    'distance': 50.0,
                    'heading': 95.0,
                    'gid': 14,
                },
            },
        ]

        directions = directions_list(features)

        assert len(directions) == 2

        first_direction = directions[0]
        assert first_direction['distance'] == 300.0
        assert first_direction['featureIndices'] == [0, 1]
        first_segment_indices = [
            segment['featureIndex'] for segment in first_direction['directionSegments']
        ]
        assert first_segment_indices == [0, 1]
        assert first_direction['directionSegments'][1]['maneuver'] == 'Turn slightly to the right'

        second_direction = directions[1]
        assert second_direction['distance'] == 100.0
        assert second_direction['featureIndices'] == [2, 3]
        second_segment_indices = [
            segment['featureIndex'] for segment in second_direction['directionSegments']
        ]
        assert second_segment_indices == [2, 3]

    def test_empty_features_returns_empty_directions(self):
        assert directions_list([]) == []

    def test_direction_text_for_first_and_last_steps(self):
        features = [
            {
                'type': 'Feature',
                'geometry': {},
                'properties': {
                    'name': 'Main Street',
                    'type': 'route',
                    'distance': 160.9344,
                    'heading': 0.0,
                    'gid': 21,
                },
            },
            {
                'type': 'Feature',
                'geometry': {},
                'properties': {
                    'name': 'Oak Avenue',
                    'type': 'route',
                    'distance': 160.9344,
                    'heading': 90.0,
                    'gid': 22,
                },
            },
        ]

        directions = directions_list(features)

        assert directions[0]['directionText'] == (
            'Head north on Main Street for 0.1 miles'
        )
        assert directions[1]['directionText'] == (
            'Turn right onto Oak Avenue and head east for 0.1 miles '
            'until you reach your destination'
        )

    def test_direction_text_for_unnamed_street(self):
        features = [
            {
                'type': 'Feature',
                'geometry': {},
                'properties': {
                    'name': 'Main Street',
                    'type': 'route',
                    'distance': 160.9344,
                    'heading': 0.0,
                    'gid': 31,
                },
            },
            {
                'type': 'Feature',
                'geometry': {},
                'properties': {
                    'name': None,
                    'type': 'route',
                    'distance': 160.9344,
                    'heading': 90.0,
                    'gid': 32,
                },
            },
        ]

        directions = directions_list(features)

        assert directions[1]['directionText'] == (
            'Turn right onto an unknown street and head east for 0.1 miles '
            'until you reach your destination'
        )
