#!/usr/bin/env python3
"""
Generate random vertex pairs and compare mellow-bike-map routing results
with and without sidewalks allowed.
"""

import argparse
import os
import sys
from pathlib import Path
from statistics import mean
from typing import Dict, List, Optional, Sequence, Tuple

try:
    from django.db import connection
except ModuleNotFoundError as exc:  # pragma: no cover - environment guard
    raise SystemExit(
        "Django is not installed. Activate the project's virtualenv before running this script."
    ) from exc


def bootstrap_django() -> None:
    """Configure Django so we can reuse the mbm Route view logic."""
    repo_root = Path(__file__).resolve().parents[1]
    app_path = repo_root / "app"
    if str(app_path) not in sys.path:
        sys.path.insert(0, str(app_path))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mbm.settings")
    import django
    django.setup()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Randomly sample vertex pairs and compare route lengths with and "
            "without sidewalks."
        )
    )
    parser.add_argument(
        "-n",
        "--num-pairs",
        type=int,
        default=50,
        help="Number of random vertex pairs to evaluate (default: 50)",
    )
    parser.add_argument(
        "--enable-v2",
        action="store_true",
        help="Run the v2 weighting logic when calling get_route()",
    )
    return parser.parse_args()


def fetch_random_vertex_pairs(num_pairs: int) -> Sequence[Tuple[int, int]]:
    """
    Fetch random vertex pairs in a single SQL query. We grab 2 * num_pairs
    rows ordered randomly and stitch them into pairs.
    """
    if num_pairs <= 0:
        return []

    total_vertices = num_pairs * 2
    with connection.cursor() as cursor:
        cursor.execute(
            """
            WITH randomized AS (
                SELECT id
                FROM chicago_ways_vertices_pgr
                ORDER BY random()
                LIMIT %s
            ),
            numbered AS (
                SELECT id, row_number() OVER () AS rn
                FROM randomized
            )
            SELECT src.id AS source_id, dst.id AS target_id
            FROM numbered src
            JOIN numbered dst
              ON dst.rn = src.rn + 1
            WHERE src.rn %% 2 = 1
            ORDER BY src.rn
            """,
            [total_vertices],
        )
        rows = cursor.fetchall()
    return rows


def parse_distance(distance_value: Optional[str]) -> Optional[float]:
    """Convert the '4.3 miles' formatted string into a float."""
    if not distance_value:
        return None
    try:
        return float(str(distance_value).split()[0])
    except (ValueError, IndexError):
        return None


def run_route(route_view, source: int, target: int, *, allow_sidewalks: bool, enable_v2: bool) -> Dict:
    """Call Route.get_route() and capture success, distance, and errors."""
    try:
        data = route_view.get_route(
            source, target, enable_v2=enable_v2, allow_sidewalks=allow_sidewalks
        )
    except Exception as exc:  # noqa: BLE001 - surface DB issues to the report
        return {
            "success": False,
            "distance": None,
            "error": str(exc),
        }

    features = data.get("features", [])
    success = bool(features)
    error = None if success else "no path returned"

    return {
        "success": success,
        "distance": parse_distance(data.get("properties", {}).get("distance")),
        "error": error,
    }


def summarize_results(results: List[Dict], num_pairs: int) -> None:
    allow_success = sum(1 for item in results if item["allow"]["success"])
    disallow_success = sum(1 for item in results if item["disallow"]["success"])

    both_success = sum(
        1 for item in results if item["allow"]["success"] and item["disallow"]["success"]
    )
    allow_only = sum(
        1 for item in results if item["allow"]["success"] and not item["disallow"]["success"]
    )
    disallow_only = sum(
        1 for item in results if not item["allow"]["success"] and item["disallow"]["success"]
    )
    both_failed = num_pairs - (both_success + allow_only + disallow_only)

    print(f"Evaluated {num_pairs} random vertex pairs.")
    print("Route success summary:")
    print(f"  allow_sidewalks=True : {allow_success} successes / {num_pairs} pairs")
    print(f"  allow_sidewalks=False: {disallow_success} successes / {num_pairs} pairs")
    print("Outcome breakdown:")
    print(f"  both succeeded                       : {both_success}")
    print(f"  only allow_sidewalks=True succeeded  : {allow_only}")
    print(f"  only allow_sidewalks=False succeeded : {disallow_only}")
    print(f"  both failed                          : {both_failed}")

    delta_candidates = []
    for item in results:
        allow_distance = item["allow"]["distance"]
        disallow_distance = item["disallow"]["distance"]
        if (
            item["allow"]["success"]
            and item["disallow"]["success"]
            and allow_distance is not None
            and disallow_distance is not None
        ):
            delta_candidates.append(
                {
                    "source": item["source"],
                    "target": item["target"],
                    "allow_distance": allow_distance,
                    "disallow_distance": disallow_distance,
                    "delta": disallow_distance - allow_distance,
                }
            )

    if delta_candidates:
        avg_delta = mean(item["delta"] for item in delta_candidates)
        avg_note = (
            "longer" if avg_delta > 0 else "shorter"
            if avg_delta < 0 else "unchanged"
        )
        print(
            f"\nAverage distance delta (no sidewalks - allow sidewalks): "
            f"{avg_delta:.3f} miles ({avg_note} on average)"
        )

        print("\nTop 10 increases when sidewalks are disallowed:")
        top_deltas = sorted(delta_candidates, key=lambda item: item["delta"], reverse=True)[:10]
        if not any(item["delta"] > 0 for item in top_deltas):
            print("  No routes got longer when sidewalks were disallowed.")
        else:
            print("  source -> target | allow (mi) | no sidewalks (mi) | delta (mi)")
            for item in top_deltas:
                print(
                    f"  {item['source']:>7} -> {item['target']:<7} | "
                    f"{item['allow_distance']:>8.3f} | "
                    f"{item['disallow_distance']:>16.3f} | "
                    f"{item['delta']:>9.3f}"
                )
    else:
        print("\nNo successful route pairs to compare distances.")

    regression_pairs = [
        item for item in results if item["allow"]["success"] and not item["disallow"]["success"]
    ]
    if regression_pairs:
        print(
            "\nPairs that regressed (success with sidewalks allowed but not without sidewalks):"
        )
        for item in regression_pairs[:10]:
            error = item["disallow"]["error"] or "unknown failure"
            print(f"  {item['source']} -> {item['target']}: {error}")


def main() -> None:
    args = parse_args()
    bootstrap_django()
    from mbm.views import Route  # pylint: disable=import-outside-toplevel

    route_view = Route()
    vertex_pairs = fetch_random_vertex_pairs(args.num_pairs)
    if len(vertex_pairs) < args.num_pairs:
        print(
            f"Warning: requested {args.num_pairs} pairs but only generated {len(vertex_pairs)} "
            "due to sampling limits."
        )

    results: List[Dict[str, Dict]] = []
    for source, target in vertex_pairs:
        allow_result = run_route(
            route_view,
            source,
            target,
            allow_sidewalks=True,
            enable_v2=args.enable_v2,
        )
        disallow_result = run_route(
            route_view,
            source,
            target,
            allow_sidewalks=False,
            enable_v2=args.enable_v2,
        )
        results.append(
            {
                "source": source,
                "target": target,
                "allow": allow_result,
                "disallow": disallow_result,
            }
        )

    summarize_results(results, len(vertex_pairs))


if __name__ == "__main__":
    main()
