from typing import TypedDict, Literal, Dict, List, Optional, Any

class RouteProperties(TypedDict, total=False):
    name: str
    type: str
    distance: float
    heading: float
    gid: int
    osm_id: int
    tag_id: int
    oneway: str
    rule: str
    priority: int
    maxspeed_forward: int
    maxspeed_backward: int
    osm_tags: Dict[str, str]
    park_name: str

class GeoJSONFeature(TypedDict):
    type: Literal["Feature"]
    geometry: Dict[str, Any]
    properties: RouteProperties

class DirectionSegment(TypedDict):
    gid: Optional[int]
    osmData: Dict[str, Any]
    maneuver: str
    cardinal: str
    distance: float
    name: Optional[str]
    effectiveName: str
    featureIndex: int

class Direction(TypedDict):
    directionSegments: List[DirectionSegment]
    name: Optional[str]
    effectiveName: str
    distance: float
    maneuver: str
    heading: float
    cardinal: str
    type: Optional[str]
    osmData: Dict[str, Any]
    featureIndices: List[int]

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
        description = 'a path'
    else:
        description = 'an unknown street'
    
    if park_name:
        description += f' inside {park_name}'
    
    return description


def heading_to_english_maneuver(
    heading: float, 
    previous_heading: Optional[float]
) -> Dict[str, str]:
    degrees = {
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
        maneuver = degrees.get(angle, {}).get('maneuver', 'Continue')
    else:
        maneuver = 'Continue'
    
    cardinal = degrees.get(nearest_45(heading), {}).get('cardinal', 'north')
    
    return {'maneuver': maneuver, 'cardinal': cardinal}


def _should_merge_segments(
    maneuver: str,
    new_segment_effective_name: str,
    previous_segment_effective_name: Optional[str],
    name: Optional[str],
) -> bool:
    # Merge continues and slight turns when two segments have the same street name
    is_slight_turn = (maneuver == 'Turn slightly to the left' or 
                     maneuver == 'Turn slightly to the right' or maneuver == 'Continue')
    is_named_street = bool(name)
    same_named_street = new_segment_effective_name == previous_segment_effective_name
    if is_slight_turn and is_named_street and same_named_street:
        return True
    
    # Merge continues on unnamed streets
    if maneuver == 'Continue' and not is_named_street:
        return True
    
    return False


def _merge_with_previous_direction(
    directions: List[Direction],
    direction_segment: DirectionSegment,
) -> None:
    if not directions:
        return

    previous_direction = directions[-1]
    previous_direction['distance'] += direction_segment['distance']
    previous_direction['directionSegments'].append(direction_segment)
    previous_direction['featureIndices'].append(direction_segment['featureIndex'])
    name = direction_segment.get('name')
    effective_name = direction_segment['effectiveName']
    osm_data = direction_segment['osmData']
    
    # Sometimes only some chicago_ways of a street are named, so check if the
    # previous chicago_way is named and backfill the name if not
    if name and not previous_direction['name']:
        previous_direction['name'] = name
        previous_direction['effectiveName'] = effective_name
    
    # For unnamed streets, preserve OSM data from the current chicago_way if previous doesn't have a name
    if not name and osm_data and not previous_direction['name']:
        previous_direction['osmData'] = osm_data
        previous_direction['effectiveName'] = effective_name


def directions_list(features: List[GeoJSONFeature]) -> List[Direction]:
    directions: List[Direction] = []
    previous_heading = None
    previous_effective_name = None
    
    for i, feature in enumerate(features):
        props: RouteProperties = feature['properties']
        name = props.get('name')
        heading: float = props.get('heading', 0.0) or 0.0
        distance: float = props.get('distance', 0)
        route_type: Optional[str] = props.get('type')
        osm_tags: Optional[Dict[str, str]] = props.get('osm_tags')
        park_name: Optional[str] = props.get('park_name')
        
        osm_data = {
            'gid': props.get('gid'),
            'osm_id': props.get('osm_id'),
            'tag_id': props.get('tag_id'),
            'oneway': props.get('oneway'),
            'rule': props.get('rule'),
            'priority': props.get('priority'),
            'maxspeed_forward': props.get('maxspeed_forward'),
            'maxspeed_backward': props.get('maxspeed_backward'),
            'length_m': distance,
            'osm_tags': osm_tags,
            'park_name': park_name,
        }
        
        maneuver_info = heading_to_english_maneuver(heading, previous_heading)
        maneuver = maneuver_info['maneuver']
        cardinal = maneuver_info['cardinal']
        
        effective_name = name or describe_unnamed_street(osm_tags, park_name)
        
        direction_segment: DirectionSegment = {
            'gid': props.get('gid'),
            'osmData': osm_data,
            'maneuver': maneuver,
            'cardinal': cardinal,
            'distance': distance,
            'name': name,
            'effectiveName': effective_name,
            'featureIndex': i,
        }
        
        direction: Direction = {
            'directionSegments': [direction_segment],
            'name': name,
            'effectiveName': effective_name,
            'distance': distance,
            'maneuver': maneuver,
            'heading': heading,
            'cardinal': cardinal,
            'type': props.get('type'),
            'osmData': osm_data,
            'featureIndices': [i],
        }
        
        if _should_merge_segments(maneuver, effective_name, previous_effective_name, name):
            _merge_with_previous_direction(directions, direction_segment)
        else:
            directions.append(direction)
        
        previous_heading = heading
        previous_effective_name = effective_name
    
    return directions
