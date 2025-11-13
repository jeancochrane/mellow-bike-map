from typing import TypedDict, Literal, Dict, Any

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