import pytest
from mbm.directions import _should_merge_segments, _merge_with_previous_direction


class TestShouldMergeSegments:
    def test_slight_turn_same_named_street_should_merge(self):
        result = _should_merge_segments(
            maneuver='Turn slightly to the right',
            new_segment_effective_name='Main Street',
            previous_segment_effective_name='Main Street',
            name='Main Street',
            previous_heading=0.0
        )
        assert result is True
    
    def test_slight_turn_left_same_named_street_should_merge(self):
        result = _should_merge_segments(
            maneuver='Turn slightly to the left',
            new_segment_effective_name='Oak Avenue',
            previous_segment_effective_name='Oak Avenue',
            name='Oak Avenue',
            previous_heading=90.0
        )
        assert result is True
    
    def test_slight_turn_different_named_street_should_not_merge(self):
        result = _should_merge_segments(
            maneuver='Turn slightly to the right',
            new_segment_effective_name='Main Street',
            previous_segment_effective_name='Oak Avenue',
            name='Main Street',
            previous_heading=0.0
        )
        assert result is False
    
    def test_slight_turn_unnamed_street_should_not_merge(self):
        result = _should_merge_segments(
            maneuver='Turn slightly to the right',
            new_segment_effective_name='an unknown street',
            previous_segment_effective_name='an unknown street',
            name=None,
            previous_heading=0.0
        )
        assert result is False
    
    def test_continue_same_street_should_merge(self):
        result = _should_merge_segments(
            maneuver='Continue',
            new_segment_effective_name='Main Street',
            previous_segment_effective_name='Main Street',
            name='Main Street',
            previous_heading=0.0
        )
        assert result is True
    
    def test_continue_different_street_should_not_merge(self):
        result = _should_merge_segments(
            maneuver='Continue',
            new_segment_effective_name='Main Street',
            previous_segment_effective_name='Oak Avenue',
            name='Main Street',
            previous_heading=0.0
        )
        assert result is False
    
    def test_turn_right_should_not_merge(self):
        result = _should_merge_segments(
            maneuver='Turn right',
            new_segment_effective_name='Main Street',
            previous_segment_effective_name='Main Street',
            name='Main Street',
            previous_heading=0.0
        )
        assert result is False
    
    def test_turn_left_should_not_merge(self):
        result = _should_merge_segments(
            maneuver='Turn left',
            new_segment_effective_name='Main Street',
            previous_segment_effective_name='Main Street',
            name='Main Street',
            previous_heading=0.0
        )
        assert result is False
    
    def test_sharp_turn_should_not_merge(self):
        result = _should_merge_segments(
            maneuver='Take a sharp right turn',
            new_segment_effective_name='Main Street',
            previous_segment_effective_name='Main Street',
            name='Main Street',
            previous_heading=0.0
        )
        assert result is False
    
    def test_turn_around_should_not_merge(self):
        result = _should_merge_segments(
            maneuver='Turn around',
            new_segment_effective_name='Main Street',
            previous_segment_effective_name='Main Street',
            name='Main Street',
            previous_heading=0.0
        )
        assert result is False
    
    def test_street_name_changed_should_not_merge(self):
        result = _should_merge_segments(
            maneuver='Continue',
            new_segment_effective_name='Oak Avenue',
            previous_segment_effective_name='Main Street',
            name='Oak Avenue',
            previous_heading=0.0
        )
        assert result is False
    
    def test_first_segment_no_previous_heading_should_not_merge(self):
        result = _should_merge_segments(
            maneuver='Continue',
            new_segment_effective_name='Main Street',
            previous_segment_effective_name=None,
            name='Main Street',
            previous_heading=None
        )
        assert result is False
    
    def test_continue_no_previous_heading_should_not_merge(self):
        result = _should_merge_segments(
            maneuver='Continue',
            new_segment_effective_name='Main Street',
            previous_segment_effective_name='Main Street',
            name='Main Street',
            previous_heading=None
        )
        assert result is False
    
    def test_slight_turn_same_unnamed_street_should_not_merge(self):
        result = _should_merge_segments(
            maneuver='Turn slightly to the right',
            new_segment_effective_name='an unknown street',
            previous_segment_effective_name='an unknown street',
            name=None,
            previous_heading=0.0
        )
        assert result is False
    
    def test_slight_turn_different_unnamed_streets_should_not_merge(self):
        result = _should_merge_segments(
            maneuver='Turn slightly to the right',
            new_segment_effective_name='an unknown street',
            previous_segment_effective_name='an alley',
            name=None,
            previous_heading=0.0
        )
        assert result is False
    
    def test_continue_unnamed_street_same_should_merge(self):
        result = _should_merge_segments(
            maneuver='Continue',
            new_segment_effective_name='an unknown street',
            previous_segment_effective_name='an unknown street',
            name=None,
            previous_heading=0.0
        )
        assert result is True
    
    def test_slight_turn_first_segment_should_not_merge(self):
        result = _should_merge_segments(
            maneuver='Turn slightly to the right',
            new_segment_effective_name='Main Street',
            previous_segment_effective_name=None,
            name='Main Street',
            previous_heading=None
        )
        assert result is False


class TestMergeWithPreviousDirection:
    def test_basic_merge(self):
        """Test basic merge: distance, chicago_way, and feature_index are added correctly"""
        directions = [{
            'name': 'Main Street',
            'effectiveName': 'Main Street',
            'distance': 100.0,
            'maneuver': 'Continue',
            'heading': 0.0,
            'cardinal': 'north',
            'type': 'route',
            'osmData': {'osm_id': 1, 'tag_id': 2},
            'osmDataChicagoWays': [{
                'osmData': {'osm_id': 1, 'tag_id': 2},
                'maneuver': 'Continue',
                'cardinal': 'north',
                'distance': 100.0,
                'name': 'Main Street',
                'effectiveName': 'Main Street',
            }],
            'featureIndices': [0],
        }]
        
        chicago_way = {
            'osmData': {'osm_id': 3, 'tag_id': 4},
            'maneuver': 'Continue',
            'cardinal': 'north',
            'distance': 50.0,
            'name': 'Main Street',
            'effectiveName': 'Main Street',
        }
        
        osm_data = {'osm_id': 3, 'tag_id': 4}
        
        _merge_with_previous_direction(
            directions, 50.0, chicago_way, 1, 'Main Street', 'Main Street', osm_data
        )
        
        assert directions[0]['distance'] == 150.0
        assert len(directions[0]['osmDataChicagoWays']) == 2
        assert directions[0]['osmDataChicagoWays'][1] == chicago_way
        assert len(directions[0]['featureIndices']) == 2
        assert directions[0]['featureIndices'][1] == 1
    
    def test_empty_directions_list(self):
        """Test empty directions list returns early without error"""
        directions = []
        
        chicago_way = {
            'osmData': {'osm_id': 1},
            'maneuver': 'Continue',
            'cardinal': 'north',
            'distance': 50.0,
            'name': 'Main Street',
            'effectiveName': 'Main Street',
        }
        
        osm_data = {'osm_id': 1}
        
        # Should not raise an error
        _merge_with_previous_direction(
            directions, 50.0, chicago_way, 1, 'Main Street', 'Main Street', osm_data
        )
        
        assert directions == []
    
    def test_name_backfill(self):
        """Test name backfilling when current has name but previous does not"""
        directions = [{
            'name': None,
            'effectiveName': 'an unknown street',
            'distance': 100.0,
            'maneuver': 'Continue',
            'heading': 0.0,
            'cardinal': 'north',
            'type': 'route',
            'osmData': {'osm_id': 1},
            'osmDataChicagoWays': [{
                'osmData': {'osm_id': 1},
                'maneuver': 'Continue',
                'cardinal': 'north',
                'distance': 100.0,
                'name': None,
                'effectiveName': 'an unknown street',
            }],
            'featureIndices': [0],
        }]
        
        chicago_way = {
            'osmData': {'osm_id': 2},
            'maneuver': 'Continue',
            'cardinal': 'north',
            'distance': 50.0,
            'name': 'Main Street',
            'effectiveName': 'Main Street',
        }
        
        osm_data = {'osm_id': 2}
        
        _merge_with_previous_direction(
            directions, 50.0, chicago_way, 1, 'Main Street', 'Main Street', osm_data
        )
        
        assert directions[0]['name'] == 'Main Street'
        assert directions[0]['effectiveName'] == 'Main Street'
    
    def test_osm_data_preservation(self):
        """Test OSM data preservation for unnamed streets"""
        directions = [{
            'name': None,
            'effectiveName': 'an unknown street',
            'distance': 100.0,
            'maneuver': 'Continue',
            'heading': 0.0,
            'cardinal': 'north',
            'type': 'route',
            'osmData': None,
            'osmDataChicagoWays': [{
                'osmData': None,
                'maneuver': 'Continue',
                'cardinal': 'north',
                'distance': 100.0,
                'name': None,
                'effectiveName': 'an unknown street',
            }],
            'featureIndices': [0],
        }]
        
        chicago_way = {
            'osmData': {'osm_id': 2, 'osm_tags': {'highway': 'service'}},
            'maneuver': 'Continue',
            'cardinal': 'north',
            'distance': 50.0,
            'name': None,
            'effectiveName': 'an access road',
        }
        
        osm_data = {'osm_id': 2, 'osm_tags': {'highway': 'service'}}
        
        _merge_with_previous_direction(
            directions, 50.0, chicago_way, 1, None, 'an access road', osm_data
        )
        
        assert directions[0]['osmData'] == osm_data
        assert directions[0]['effectiveName'] == 'an access road'
    
    def test_multiple_merges(self):
        """Test multiple merges accumulate correctly"""
        directions = [{
            'name': 'Main Street',
            'effectiveName': 'Main Street',
            'distance': 100.0,
            'maneuver': 'Continue',
            'heading': 0.0,
            'cardinal': 'north',
            'type': 'route',
            'osmData': {'osm_id': 1},
            'osmDataChicagoWays': [{
                'osmData': {'osm_id': 1},
                'maneuver': 'Continue',
                'cardinal': 'north',
                'distance': 100.0,
                'name': 'Main Street',
                'effectiveName': 'Main Street',
            }],
            'featureIndices': [0],
        }]
        
        chicago_way1 = {
            'osmData': {'osm_id': 2},
            'maneuver': 'Continue',
            'cardinal': 'north',
            'distance': 50.0,
            'name': 'Main Street',
            'effectiveName': 'Main Street',
        }
        
        chicago_way2 = {
            'osmData': {'osm_id': 3},
            'maneuver': 'Continue',
            'cardinal': 'north',
            'distance': 75.0,
            'name': 'Main Street',
            'effectiveName': 'Main Street',
        }
        
        osm_data1 = {'osm_id': 2}
        osm_data2 = {'osm_id': 3}
        
        _merge_with_previous_direction(
            directions, 50.0, chicago_way1, 1, 'Main Street', 'Main Street', osm_data1
        )
        _merge_with_previous_direction(
            directions, 75.0, chicago_way2, 2, 'Main Street', 'Main Street', osm_data2
        )
        
        assert directions[0]['distance'] == 225.0
        assert len(directions[0]['osmDataChicagoWays']) == 3
        assert len(directions[0]['featureIndices']) == 3
        assert directions[0]['featureIndices'] == [0, 1, 2]
    
    def test_no_name_backfill_when_previous_has_name(self):
        """Test name isn't overwritten if previous already has one"""
        directions = [{
            'name': 'Main Street',
            'effectiveName': 'Main Street',
            'distance': 100.0,
            'maneuver': 'Continue',
            'heading': 0.0,
            'cardinal': 'north',
            'type': 'route',
            'osmData': {'osm_id': 1},
            'osmDataChicagoWays': [{
                'osmData': {'osm_id': 1},
                'maneuver': 'Continue',
                'cardinal': 'north',
                'distance': 100.0,
                'name': 'Main Street',
                'effectiveName': 'Main Street',
            }],
            'featureIndices': [0],
        }]
        
        chicago_way = {
            'osmData': {'osm_id': 2},
            'maneuver': 'Continue',
            'cardinal': 'north',
            'distance': 50.0,
            'name': 'Oak Avenue',
            'effectiveName': 'Oak Avenue',
        }
        
        osm_data = {'osm_id': 2}
        
        _merge_with_previous_direction(
            directions, 50.0, chicago_way, 1, 'Oak Avenue', 'Oak Avenue', osm_data
        )
        
        # Name should remain 'Main Street', not be overwritten
        assert directions[0]['name'] == 'Main Street'
        assert directions[0]['effectiveName'] == 'Main Street'
    
    def test_no_osm_data_update_when_previous_has_name(self):
        """Test OSM data isn't updated for unnamed streets when previous has a name"""
        directions = [{
            'name': 'Main Street',
            'effectiveName': 'Main Street',
            'distance': 100.0,
            'maneuver': 'Continue',
            'heading': 0.0,
            'cardinal': 'north',
            'type': 'route',
            'osmData': {'osm_id': 1},
            'osmDataChicagoWays': [{
                'osmData': {'osm_id': 1},
                'maneuver': 'Continue',
                'cardinal': 'north',
                'distance': 100.0,
                'name': 'Main Street',
                'effectiveName': 'Main Street',
            }],
            'featureIndices': [0],
        }]
        
        chicago_way = {
            'osmData': {'osm_id': 2, 'osm_tags': {'highway': 'service'}},
            'maneuver': 'Continue',
            'cardinal': 'north',
            'distance': 50.0,
            'name': None,
            'effectiveName': 'an access road',
        }
        
        osm_data = {'osm_id': 2, 'osm_tags': {'highway': 'service'}}
        original_osm_data = directions[0]['osmData'].copy()
        
        _merge_with_previous_direction(
            directions, 50.0, chicago_way, 1, None, 'an access road', osm_data
        )
        
        # OSM data should not be updated when previous has a name
        assert directions[0]['osmData'] == original_osm_data
        assert directions[0]['effectiveName'] == 'Main Street'

