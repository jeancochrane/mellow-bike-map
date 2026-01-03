#!/usr/bin/env python3
"""
Generate random vertex pairs and compare mellow-bike-map routing results
with different sidewalk penalty values (None, 2, and 5).
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
# Test penalty scenarios: None (no penalty), 2 (double cost), 5 (5x cost), 10 (10x cost)
PENALTIES = [None, 2, 5, 10]


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


def count_sidewalk_ways(route_data: Dict) -> int:
    """
    Count the number of sidewalk ways in a route.
    
    Uses the osm_ids from the route features to query which ways are sidewalks.
    
    Args:
        route_data: The route GeoJSON returned from Route.get_route()
    
    Returns:
        Number of distinct sidewalk ways in the route
    """
    features = route_data.get("features", [])
    if not features:
        return 0
    
    # Get distinct osm_ids from the route
    osm_ids = list(set(
        f["properties"]["osm_id"]
        for f in features
        if f.get("properties", {}).get("osm_id")
    ))
    
    if not osm_ids:
        return 0
    
    try:
        with connection.cursor() as cursor:
            # Count how many of the route's osm_ids are sidewalks
            cursor.execute("""
                SELECT COUNT(DISTINCT osm_way.osm_id)
                FROM osm_ways AS osm_way
                WHERE osm_way.osm_id = ANY(%s)
                AND (
                    osm_way.tags @> 'footway=>sidewalk'::hstore OR
                    osm_way.tags @> 'footway=>crossing'::hstore OR
                    osm_way.tags @> 'highway=>footway'::hstore
                )
                AND NOT (
                    osm_way.tags @> 'bicycle=>permissive'::hstore OR
                    osm_way.tags @> 'bicycle=>yes'::hstore
                )
            """, [osm_ids])
            row = cursor.fetchone()
            return row[0] if row else 0
    except Exception:
        return 0


def run_route(route_view, source: int, target: int, sidewalk_penalty: Optional[float]) -> Dict:
    """
    Run a route calculation with a specific sidewalk penalty and return success status, distance, and sidewalk count.
    
    Args:
        route_view: The Route view instance
        source: Source vertex ID
        target: Target vertex ID
        sidewalk_penalty: Penalty multiplier for sidewalks (None = no penalty)
    
    Returns: {"success": bool, "distance": float|None, "error": str|None, "sidewalk_count": int}
    """
    try:
        data = route_view.get_route(
            source, target, enable_v2=ENABLE_V2, sidewalk_penalty=sidewalk_penalty
        )
    except Exception as exc:  # noqa: BLE001 - surface DB issues to the report
        return {
            "success": False,
            "distance": None,
            "error": str(exc),
            "sidewalk_count": 0,
        }

    features = data.get("features", [])
    success = bool(features)
    error = None if success else "no path returned"
    
    # Count sidewalk ways from the returned route data
    sidewalk_count = count_sidewalk_ways(data) if success else 0

    return {
        "success": success,
        "distance": parse_distance(data.get("properties", {}).get("distance")),
        "error": error,
        "sidewalk_count": sidewalk_count,
    }


def summarize_results(results: List[Dict]) -> None:
    """Print a simple summary comparing routes with different sidewalk penalties."""
    num_pairs = len(results)
    
    # Count successes for each penalty
    success_counts = {}
    for penalty in PENALTIES:
        penalty_key = "none" if penalty is None else str(penalty)
        success_counts[penalty_key] = sum(
            1 for r in results if r[penalty_key]["success"]
        )
    
    print(f"\nEvaluated {num_pairs} random vertex pairs")
    print("Success rates by sidewalk penalty:")
    for penalty in PENALTIES:
        penalty_key = "none" if penalty is None else str(penalty)
        penalty_label = "None (no penalty)" if penalty is None else f"{penalty}x"
        print(f"  {penalty_label:20s}: {success_counts[penalty_key]}/{num_pairs} succeeded")
    
    # Calculate average sidewalk counts for successful routes
    print("\nAverage sidewalk ways per route (for successful routes):")
    for penalty in PENALTIES:
        penalty_key = "none" if penalty is None else str(penalty)
        penalty_label = "None (no penalty)" if penalty is None else f"{penalty}x"
        successful_routes = [r for r in results if r[penalty_key]["success"]]
        if successful_routes:
            avg_sidewalks = sum(r[penalty_key]["sidewalk_count"] for r in successful_routes) / len(successful_routes)
            print(f"  {penalty_label:20s}: {avg_sidewalks:.2f} sidewalk ways")
        else:
            print(f"  {penalty_label:20s}: N/A (no successful routes)")
    
    # Count routes that include at least one sidewalk
    print("\nRoutes that include at least one sidewalk (for successful routes):")
    for penalty in PENALTIES:
        penalty_key = "none" if penalty is None else str(penalty)
        penalty_label = "None (no penalty)" if penalty is None else f"{penalty}x"
        successful_routes = [r for r in results if r[penalty_key]["success"]]
        if successful_routes:
            routes_with_sidewalks = sum(1 for r in successful_routes if r[penalty_key]["sidewalk_count"] > 0)
            percentage = (routes_with_sidewalks / len(successful_routes)) * 100
            print(f"  {penalty_label:20s}: {routes_with_sidewalks}/{len(successful_routes)} ({percentage:.1f}%)")
        else:
            print(f"  {penalty_label:20s}: N/A (no successful routes)")
    
    # Find pairs that succeeded with all penalties
    penalty_keys = ["none"] + [str(p) for p in PENALTIES if p is not None]
    all_success = sum(
        1 for r in results
        if all([r[key]["success"] for key in penalty_keys])
    )
    print(f"\nPairs that succeeded with all penalties: {all_success}/{num_pairs}")
    
    # Compare distances for routes that succeeded with all penalties
    distances = []
    for r in results:
        if all([r[key]["success"] for key in penalty_keys]):
            dists = {key: r[key]["distance"] for key in penalty_keys}
            if all(d is not None for d in dists.values()):
                distance_entry = {
                    "source": r["source"],
                    "target": r["target"],
                    "none": dists["none"],
                }
                for key in penalty_keys:
                    if key != "none":
                        distance_entry[f"penalty{key}"] = dists[key]
                        distance_entry[f"delta_{key}"] = dists[key] - dists["none"]
                distances.append(distance_entry)
    
    if distances:
        print(f"\nDistance comparison ({len(distances)} pairs that succeeded with all penalties):")
        for key in penalty_keys:
            if key != "none":
                delta_key = f"delta_{key}"
                if delta_key in distances[0]:
                    avg_delta = sum(d[delta_key] for d in distances) / len(distances)
                    penalty_label = f"{key}x"
                    print(f"  Average difference (penalty={penalty_label} vs none): {avg_delta:+.3f} miles")
                    if avg_delta > 0:
                        print(f"    (Routes with {penalty_label} penalty are {avg_delta:.3f} miles longer on average)")
                    elif avg_delta < 0:
                        print(f"    (Routes with {penalty_label} penalty are {abs(avg_delta):.3f} miles shorter on average)")
    
    # Find regressions (worked with no penalty but failed with penalty)
    regressions = {}
    for key in penalty_keys:
        if key != "none":
            regressions[key] = sum(
                1 for r in results
                if r["none"]["success"] and not r[key]["success"]
            )
    
    total_regressions = sum(regressions.values())
    if total_regressions > 0:
        print(f"\nRegressions (succeeded with no penalty but failed with penalty):")
        for key in penalty_keys:
            if key != "none":
                penalty_label = f"{key}x"
                print(f"  Failed with penalty={penalty_label}: {regressions[key]}")
        
        # Show regression examples
        for key in penalty_keys:
            if key != "none" and regressions[key] > 0:
                penalty_label = f"{key}x"
                print(f"\nRegression examples with penalty={penalty_label} (first 3):")
                count = 0
                for r in results:
                    if r["none"]["success"] and not r[key]["success"]:
                        error = r[key]["error"] or "unknown"
                        print(f"  {r['source']} -> {r['target']}: {error}")
                        count += 1
                        if count >= 3:
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
    
    # Run routes for each pair with different penalties
    results = []
    total = len(vertex_pairs)
    print(f"\nProcessing {total} pairs with {len(PENALTIES)} penalty scenarios...")
    
    for i, (source, target) in enumerate(vertex_pairs, 1):
        # Show progress: [X/Y] source -> target
        percent = int((i / total) * 100)
        sys.stdout.write(f"\r[{i}/{total}] ({percent}%) {source} -> {target} ... ")
        sys.stdout.flush()
        
        # Run route calculations with each penalty
        result = {
            "source": source,
            "target": target,
        }
        
        for penalty in PENALTIES:
            penalty_key = "none" if penalty is None else str(penalty)
            penalty_result = run_route(route_view, source, target, sidewalk_penalty=penalty)
            result[penalty_key] = penalty_result
        
        # Show quick status for all penalties
        statuses = []
        for penalty in PENALTIES:
            penalty_key = "none" if penalty is None else str(penalty)
            status = "✓" if result[penalty_key]["success"] else "✗"
            statuses.append(status)
        sys.stdout.write("/".join(statuses))
        sys.stdout.flush()
        
        results.append(result)
    
    # Clear the progress line and print completion
    sys.stdout.write("\r" + " " * 80 + "\r")  # Clear line
    print(f"Completed processing {total} pairs\n")
    
    # Print summary
    summarize_results(results)


if __name__ == "__main__":
    main()

