import json
from typing import List

from django.core.management.base import BaseCommand, CommandError
from mbm.directions import directions_list
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
        if not features:
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
