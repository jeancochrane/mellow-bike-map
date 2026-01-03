#!/usr/bin/env python3
"""
Generate random vertex pairs and compare mellow-bike-map routing results
with and without sidewalks allowed.
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    from django.db import connection
except ModuleNotFoundError as exc:
    raise SystemExit(
        "Django is not installed. Activate the project's virtualenv before running this script."
    ) from exc


# Configuration: hardcoded defaults
NUM_PAIRS = 20
ENABLE_V2 = False


def bootstrap_django() -> None:
    """Configure Django so we can reuse the mbm Route view logic."""
    repo_root = Path(__file__).resolve().parents[1]
    app_path = repo_root / "app"
    if str(app_path) not in sys.path:
        sys.path.insert(0, str(app_path))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mbm.settings")
    import django
    django.setup()


def fetch_random_vertex_pairs(num_pairs: int) -> List[Tuple[int, int]]:
    """
    Fetch random vertex pairs from the database.
    
    Strategy: Get 2*num_pairs random vertices, number them, then pair up
    consecutive rows (1->2, 3->4, 5->6, etc.) to create num_pairs.
    """
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


def run_route(route_view, source: int, target: int, allow_sidewalks: bool) -> Dict:
    """
    Run a route calculation and return success status and distance.
    
    Returns: {"success": bool, "distance": float|None, "error": str|None}
    """
    try:
        data = route_view.get_route(
            source, target, enable_v2=ENABLE_V2, allow_sidewalks=allow_sidewalks
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


def summarize_results(results: List[Dict]) -> None:
    """Print a simple summary of the route comparison results."""
    num_pairs = len(results)
    
    # Count successes
    allow_success = sum(1 for r in results if r["allow"]["success"])
    disallow_success = sum(1 for r in results if r["disallow"]["success"])
    both_success = sum(1 for r in results if r["allow"]["success"] and r["disallow"]["success"])
    regressions = sum(1 for r in results if r["allow"]["success"] and not r["disallow"]["success"])
    
    print(f"\nEvaluated {num_pairs} random vertex pairs")
    print(f"  With sidewalks:    {allow_success}/{num_pairs} succeeded")
    print(f"  Without sidewalks: {disallow_success}/{num_pairs} succeeded")
    print(f"  Both succeeded:    {both_success}")
    print(f"  Regressions:        {regressions} (worked with sidewalks, failed without)")
    
    # Compare distances for routes that succeeded both ways
    distances = []
    for r in results:
        if r["allow"]["success"] and r["disallow"]["success"]:
            allow_dist = r["allow"]["distance"]
            disallow_dist = r["disallow"]["distance"]
            if allow_dist is not None and disallow_dist is not None:
                distances.append({
                    "source": r["source"],
                    "target": r["target"],
                    "allow": allow_dist,
                    "disallow": disallow_dist,
                    "delta": disallow_dist - allow_dist,
                })
    
    if distances:
        avg_delta = sum(d["delta"] for d in distances) / len(distances)
        print(f"\nDistance comparison ({len(distances)} pairs that succeeded both ways):")
        print(f"  Average difference: {avg_delta:.3f} miles")
        if avg_delta > 0:
            print(f"  (Routes are {avg_delta:.3f} miles longer on average without sidewalks)")
        elif avg_delta < 0:
            print(f"  (Routes are {abs(avg_delta):.3f} miles shorter on average without sidewalks)")
        else:
            print("  (No difference on average)")
    
    # Show regressions if any
    if regressions > 0:
        print(f"\nRegression examples (first 5):")
        count = 0
        for r in results:
            if r["allow"]["success"] and not r["disallow"]["success"]:
                error = r["disallow"]["error"] or "unknown"
                print(f"  {r['source']} -> {r['target']}: {error}")
                count += 1
                if count >= 5:
                    break


def main() -> None:
    """Main execution: bootstrap Django, fetch pairs, run routes, summarize."""
    # Setup Django
    bootstrap_django()
    from mbm.views import Route
    route_view = Route()
    
    # Fetch random vertex pairs
    vertex_pairs = fetch_random_vertex_pairs(NUM_PAIRS)
    print(f"Fetched {len(vertex_pairs)} vertex pairs")
    
    # Run routes for each pair (with and without sidewalks)
    results = []
    total = len(vertex_pairs)
    print(f"\nProcessing {total} pairs...")
    
    for i, (source, target) in enumerate(vertex_pairs, 1):
        # Show progress: [X/Y] source -> target
        percent = int((i / total) * 100)
        sys.stdout.write(f"\r[{i}/{total}] ({percent}%) {source} -> {target} ... ")
        sys.stdout.flush()
        
        # Run both route calculations
        allow_result = run_route(route_view, source, target, allow_sidewalks=True)
        disallow_result = run_route(route_view, source, target, allow_sidewalks=False)
        
        # Show quick status
        allow_status = "✓" if allow_result["success"] else "✗"
        disallow_status = "✓" if disallow_result["success"] else "✗"
        sys.stdout.write(f"{allow_status}/{disallow_status}")
        sys.stdout.flush()
        
        results.append({
            "source": source,
            "target": target,
            "allow": allow_result,
            "disallow": disallow_result,
        })
    
    # Clear the progress line and print completion
    sys.stdout.write("\r" + " " * 80 + "\r")  # Clear line
    print(f"Completed processing {total} pairs\n")
    
    # Print summary
    summarize_results(results)


if __name__ == "__main__":
    main()
