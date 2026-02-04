import json
from typing import List, Optional, Tuple

from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from mbm.directions import directions_list
from mbm.models import fetchall
from mbm.routing import calculate_route, get_nearest_vertex_id


def parse_coordinate_param(value: str) -> List[float]:
    if not value:
        raise CommandError("Coordinate value is required.")
    parts = value.split(",")
    if len(parts) != 2:
        raise CommandError("Coordinate must be in 'lat,lng' format.")
    try:
        lat = float(parts[0])
        lng = float(parts[1])
    except ValueError as exc:
        raise CommandError("Coordinate must be in 'lat,lng' format.") from exc
    return [lat, lng]


def get_component_info(
    vertex_id: int,
) -> Tuple[Optional[int], Optional[int], Optional[int], Optional[int]]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            WITH components AS (
                SELECT node, component
                FROM pgr_connectedComponents(
                    'SELECT gid AS id, source, target, cost, reverse_cost FROM chicago_ways'
                )
            ),
            component_counts AS (
                SELECT component, COUNT(*) AS component_node_count
                FROM components
                GROUP BY component
            ),
            total AS (
                SELECT
                    COUNT(*) AS total_components,
                    SUM(component_node_count) AS total_nodes
                FROM component_counts
            )
            SELECT
                components.component,
                component_counts.component_node_count,
                total.total_components AS total_components,
                total.total_nodes AS total_nodes
            FROM components
            JOIN component_counts
            ON components.component = component_counts.component
            CROSS JOIN total
            WHERE node = %s
            """,
            [vertex_id],
        )
        rows = fetchall(cursor)
    if not rows:
        return None, None, None, None
    return (
        rows[0]["component"],
        rows[0]["component_node_count"],
        rows[0]["total_components"],
        rows[0]["total_nodes"],
    )


def check_vertices_connected(
    source_vertex_id: int, target_vertex_id: int
) -> Tuple[
    bool,
    Optional[int],
    Optional[int],
    Optional[int],
    Optional[int],
    Optional[int],
    Optional[int],
]:
    source_component, source_node_count, source_total_components, source_total_nodes = (
        get_component_info(source_vertex_id)
    )
    target_component, target_node_count, target_total_components, target_total_nodes = (
        get_component_info(target_vertex_id)
    )
    connected = (
        source_component is not None
        and target_component is not None
        and source_component == target_component
    )
    total_components = (
        source_total_components
        if source_total_components is not None
        else target_total_components
    )
    total_nodes = (
        source_total_nodes
        if source_total_nodes is not None
        else target_total_nodes
    )
    return (
        connected,
        source_component,
        target_component,
        source_node_count,
        target_node_count,
        total_components,
        total_nodes,
    )


class Command(BaseCommand):
    help = "Generate directions from coordinate inputs."

    def add_arguments(self, parser):
        parser.add_argument(
            "--sourceCoordinates",
            required=True,
            help="Source coordinate in 'lat,lng' format.",
        )
        parser.add_argument(
            "--targetCoordinates",
            required=True,
            help="Target coordinate in 'lat,lng' format.",
        )
        parser.add_argument(
            "--enable-v2",
            action="store_true",
            help="Enable the v2 routing costs.",
        )

    def handle(self, *_args, **options):
        source_coord = parse_coordinate_param(options["sourceCoordinates"])
        target_coord = parse_coordinate_param(options["targetCoordinates"])
        enable_v2 = options["enable_v2"]

        source_vertex_id = get_nearest_vertex_id(source_coord)
        target_vertex_id = get_nearest_vertex_id(target_coord)

        self.stdout.write(f"Source vertex id: {source_vertex_id}")
        self.stdout.write(f"Target vertex id: {target_vertex_id}")

        features, _, _ = calculate_route(
            source_vertex_id,
            target_vertex_id,
            enable_v2,
        )
        (
            connected,
            source_component,
            target_component,
            source_node_count,
            target_node_count,
            total_components,
            total_nodes,
        ) = check_vertices_connected(source_vertex_id, target_vertex_id)
        self.stdout.write(
            f"Source component: {source_component}"
        )
        self.stdout.write(
            f"Target component: {target_component}"
        )
        if source_component is not None and total_nodes:
            source_percentage = round((source_node_count / total_nodes) * 100)
            self.stdout.write(
                f"Source component node count: {source_node_count} / {total_nodes} total ({source_percentage}%)"
            )
        if target_component is not None and total_nodes:
            target_percentage = round((target_node_count / total_nodes) * 100)
            self.stdout.write(
                f"Target component node count: {target_node_count} / {total_nodes} total ({target_percentage}%)"
            )
        self.stdout.write(
            f"Total components in graph: {total_components}"
        )
        if not features:
            if connected:
                self.stdout.write(
                    "Vertices are in the same connected component, but no route was returned."
                )
            else:
                self.stdout.write(
                    "Vertices are in different connected components."
                )
            raise CommandError(
                "No route found between source and target coordinates."
            )
        # Print basic route information
        total_distance = sum(
            feature.get("properties", {}).get("length_m", 0) for feature in features
        )
        num_segments = len(features)
        self.stdout.write("Route information:")
        self.stdout.write(f"  Number of segments: {num_segments}")
        self.stdout.write(f"  Total distance: {total_distance:.1f} meters")

        directions = directions_list(features)
        if not directions:
            raise CommandError("No directions generated from route features.")

        lines = []
        for direction in directions:
            direction_text = direction.get("directionText", "")
            lines.append(direction_text)

            for segment in direction.get("directionSegments", []):
                feature_index = segment.get("featureIndex")
                gid = segment.get("gid")
                name = (
                    segment.get("name")
                    or segment.get("effectiveName")
                    or "an unknown street"
                )
                distance = segment.get("distance", 0)
                lines.append(
                    f"  way {feature_index}: {name} (gid: {gid}; distance: {distance}m)"
                )

        if not lines:
            raise CommandError("No direction text was produced.")

        self.stdout.write("\n".join(lines))
