import pytest
from mbm.directions import _should_merge_segments


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

