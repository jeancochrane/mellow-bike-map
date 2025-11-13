from typing import Dict, List, Optional, Any


def nearest_45(x: float) -> int:
    """Round an angle to the nearest 45-degree increment (0-360)."""
    return (round(x / 45) * 45) % 360

def describe_unnamed_street(
    osm_tags: Optional[Dict[str, str]], 
    park_name: Optional[str]
) -> str:
    if not osm_tags or not isinstance(osm_tags, dict):
        return 'an unknown street'
    
    description = ''
    
    if osm_tags.get('highway') == 'service' and osm_tags.get('service') == 'alley':
        description = 'an alley'
    elif osm_tags.get('highway') == 'service':
        description = 'an access road'
    elif osm_tags.get('footway') == 'crossing':
        description = 'a crosswalk'
    elif osm_tags.get('highway') == 'footway' and osm_tags.get('footway') == 'sidewalk':
        description = 'a sidewalk'
    elif park_name:
        # If inside a park and no specific description, call it a path
        description = 'a path'
    else:
        description = 'an unknown street'
    
    # Add park name if the street is within a park
    if park_name:
        description += f' inside {park_name}'
    
    return description


def heading_to_english_maneuver(
    heading: float, 
    previous_heading: Optional[float]
) -> Dict[str, str]:
    maneuvers = {
        0: {'maneuver': 'Continue', 'cardinal': 'north'},
        45: {'maneuver': 'Turn slightly to the right', 'cardinal': 'northeast'},
        90: {'maneuver': 'Turn right', 'cardinal': 'east'},
        135: {'maneuver': 'Take a sharp right turn', 'cardinal': 'southeast'},
        180: {'maneuver': 'Turn around', 'cardinal': 'south'},
        225: {'maneuver': 'Take a sharp left turn', 'cardinal': 'southwest'},
        270: {'maneuver': 'Turn left', 'cardinal': 'west'},
        315: {'maneuver': 'Turn slightly to the left', 'cardinal': 'northwest'},
    }
    
    if previous_heading is not None:
        angle = nearest_45(((heading - previous_heading) + 360) % 360)
        maneuver = maneuvers.get(angle, {}).get('maneuver', 'Continue')
    else:
        maneuver = 'Continue'
    
    cardinal = maneuvers.get(nearest_45(heading), {}).get('cardinal', 'north')
    
    return {'maneuver': maneuver, 'cardinal': cardinal}


def _should_merge_segments(
    maneuver: str,
    new_segment_effective_name: str,
    previous_segment_effective_name: Optional[str],
    name: Optional[str],
    previous_heading: Optional[float]
) -> bool:
    # Determine if this is a slight turn that can be collapsed
    is_slight_turn = (maneuver == 'Turn slightly to the left' or 
                     maneuver == 'Turn slightly to the right')
    same_named_street = new_segment_effective_name == previous_segment_effective_name
    is_named_street = bool(name)  # Only collapse slight turns for actual named streets
    should_collapse_slight_turn = is_slight_turn and same_named_street and is_named_street
    
    # If the street name changed or there's a turn to be made, add a new direction to the list
    # Exception: collapse slight turns on the same named street
    street_name_changed = bool(previous_segment_effective_name and new_segment_effective_name != previous_segment_effective_name)
    turn_required = (maneuver != 'Continue' or previous_heading is None)
    
    # Collapse if it's NOT the case that (name changed or turn required) AND it's not a slight turn to collapse
    return not ((street_name_changed or turn_required) and not should_collapse_slight_turn)


def _merge_with_previous_direction(
    directions: List[Dict[str, Any]],
    distance: float,
    chicago_way: Dict[str, Any],
    feature_index: int,
    name: Optional[str],
    effective_name: str,
    osm_data: Dict[str, Any]
) -> None:
    if not directions:
        return
    
    directions[-1]['distance'] += distance
    directions[-1]['osmDataChicagoWays'].append(chicago_way)
    directions[-1]['featureIndices'].append(feature_index)
    
    # Sometimes only some chicago_ways of a street are named, so check if the
    # previous chicago_way is named and backfill the name if not
    if name and not directions[-1]['name']:
        directions[-1]['name'] = name
        directions[-1]['effectiveName'] = effective_name
    
    # For unnamed streets, preserve OSM data from the current chicago_way if previous doesn't have a name
    if not name and osm_data and not directions[-1]['name']:
        directions[-1]['osmData'] = osm_data
        directions[-1]['effectiveName'] = effective_name


def directions_list(features: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    directions: List[Dict[str, Any]] = []
    previous_heading = None
    previous_effective_name = None
    
    for i, feature in enumerate(features):
        props = feature.get('properties', {})
        name = props.get('name')
        heading = props.get('heading')
        distance = props.get('distance', 0)
        route_type = props.get('type')
        
        osm_data = {
            'osm_id': props.get('osm_id'),
            'tag_id': props.get('tag_id'),
            'oneway': props.get('oneway'),
            'rule': props.get('rule'),
            'priority': props.get('priority'),
            'maxspeed_forward': props.get('maxspeed_forward'),
            'maxspeed_backward': props.get('maxspeed_backward'),
            'length_m': distance,
            'osm_tags': props.get('osm_tags'),
            'park_name': props.get('park_name'),
        }
        
        maneuver_info = heading_to_english_maneuver(heading, previous_heading)
        maneuver = maneuver_info['maneuver']
        cardinal = maneuver_info['cardinal']
        
        effective_name = name or describe_unnamed_street(osm_data.get('osm_tags'), osm_data.get('park_name'))
        
        chicago_way = {
            'osmData': osm_data,
            'maneuver': maneuver,
            'cardinal': cardinal,
            'distance': distance,
            'name': name,
            'effectiveName': effective_name,
        }
        
        direction = {
            'name': name,
            'effectiveName': effective_name,
            'distance': distance,
            'maneuver': maneuver,
            'heading': heading,
            'cardinal': cardinal,
            'type': route_type,
            'osmData': osm_data,
            'osmDataChicagoWays': [chicago_way],
            'featureIndices': [i],
        }
        
        if _should_merge_segments(maneuver, effective_name, previous_effective_name, name, previous_heading):
            _merge_with_previous_direction(
                directions, distance, chicago_way, i, name, effective_name, osm_data
            )
        else:
            directions.append(direction)
        
        previous_heading = heading
        previous_effective_name = effective_name
    
    return directions

