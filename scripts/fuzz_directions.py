#!/usr/bin/env python3
"""
Fuzz routing/direction generation by sampling random vertex pairs and reporting
on segments that still display as "Unnamed street" in the resulting directions.
"""

from __future__ import annotations

import argparse
import os
import random
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[1]


def _find_project_root() -> Path:
    candidates = [
        REPO_ROOT / 'app',
        REPO_ROOT,
        SCRIPT_PATH.parents[0],
    ]
    for candidate in candidates:
        if (candidate / 'mbm').exists():
            return candidate
    raise RuntimeError(
        'Unable to locate the mbm package. Ensure this script is run from the '
        'repository or set PYTHONPATH accordingly.'
    )


PROJECT_ROOT = _find_project_root()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mbm.settings')

import django  # type: ignore

django.setup()

from django.db import connection  # type: ignore

from mbm.directions import Direction, DirectionSegment, directions_list
from mbm.routing import calculate_route

TagKey = Tuple[Tuple[str, str], ...]
EFFECTIVELY_UNNAMED_LABELS = {'an unknown street', 'unnamed street'}
TAG_SET_COUNT_CACHE: Dict[TagKey, int] = {}


@dataclass(frozen=True)
class RunRecord:
    run_number: int
    source_vertex_id: int
    target_vertex_id: int
    enable_v2: bool
    distance: str
    time: str
    directions: List[Direction]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Randomly sample vertex pairs, calculate routes, and '
                    'report on unnamed street usage.'
    )
    parser.add_argument(
        '--runs',
        type=int,
        default=100,
        help='Number of random vertex pairs to test (default: 100).'
    )
    parser.add_argument(
        '--enable-v2',
        action='store_true',
        help='Enable the v2 mellow routing adjustments.'
    )
    parser.add_argument(
        '--seed',
        type=float,
        default=None,
        help='Optional seed (0.0-1.0) forwarded to Postgres setseed() for '
             'deterministic vertex sampling.'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Print per-run status details.'
    )
    return parser.parse_args()


def maybe_set_pg_seed(seed: Optional[float]) -> None:
    if seed is None:
        return
    if not 0.0 <= seed <= 1.0:
        raise ValueError('--seed must be between 0.0 and 1.0 inclusive.')
    with connection.cursor() as cursor:
        cursor.execute('SELECT setseed(%s)', [seed])


def get_random_vertex_pair() -> Tuple[int, int]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id
            FROM chicago_ways_vertices_pgr
            ORDER BY random()
            LIMIT 2
            """
        )
        rows = cursor.fetchall()
    if len(rows) < 2:
        raise RuntimeError('Unable to retrieve two vertices from the database.')
    source, target = (int(rows[0][0]), int(rows[1][0]))
    return source, target


def format_tag_key(tag_key: TagKey) -> str:
    return ', '.join(f'{key}={value}' for key, value in tag_key)


def format_tags_dict(tags: Dict[str, str]) -> str:
    if not tags:
        return '<none>'
    return ', '.join(f'{key}={tags[key]}' for key in sorted(tags))


def is_effectively_unnamed(segment: DirectionSegment) -> bool:
    effective_name = (segment.get('effectiveName') or '').strip().lower()
    return effective_name in EFFECTIVELY_UNNAMED_LABELS


def count_chicago_ways_for_tag_key(tag_key: TagKey) -> int:
    if tag_key in TAG_SET_COUNT_CACHE:
        return TAG_SET_COUNT_CACHE[tag_key]

    tag_dict = dict(tag_key)
    if not tag_dict:
        TAG_SET_COUNT_CACHE[tag_key] = 0
        return 0

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM chicago_ways AS way
            JOIN osm_ways AS osm ON way.osm_id = osm.osm_id
            WHERE osm.tags = %s
            """,
            [tag_dict],
        )
        row = cursor.fetchone()

    total = int(row[0]) if row else 0
    TAG_SET_COUNT_CACHE[tag_key] = total
    return total


def fuzz_directions(
    runs: int,
    enable_v2: bool,
    rng: random.Random,
    verbose: bool,
) -> Dict[str, object]:
    successes = 0
    failures = 0
    unnamed_segment_count = 0
    unnamed_tag_counter: Counter[TagKey] = Counter()
    runs_with_unnamed: List[RunRecord] = []

    print(f'Fuzzing {runs} routes with enable_v2={enable_v2}')

    for run_number in range(1, runs + 1):
        try:
            source_vertex_id, target_vertex_id = get_random_vertex_pair()
        except Exception as exc:
            failures += 1
            if verbose:
                print(f'[run {run_number}] failed to pick vertices: {exc}')
            continue

        try:
            features, distance, time = calculate_route(
                source_vertex_id,
                target_vertex_id,
                enable_v2,
            )
        except Exception as exc:
            failures += 1
            if verbose:
                print(
                    f'[run {run_number}] routing failed '
                    f'({source_vertex_id}->{target_vertex_id}): {exc}'
                )
            continue

        if not features:
            failures += 1
            if verbose:
                print(
                    f'[run {run_number}] no features for '
                    f'{source_vertex_id}->{target_vertex_id}'
                )
            continue

        try:
            directions = directions_list(features)
        except Exception as exc:
            failures += 1
            if verbose:
                print(f'[run {run_number}] directions_list failed: {exc}')
            continue

        successes += 1
        run_record = RunRecord(
            run_number=run_number,
            source_vertex_id=source_vertex_id,
            target_vertex_id=target_vertex_id,
            enable_v2=enable_v2,
            distance=distance,
            time=time,
            directions=directions,
        )

        run_has_unnamed_segments = False
        for direction in directions:
            for segment in direction.get('directionSegments', []):
                if not is_effectively_unnamed(segment):
                    continue
                run_has_unnamed_segments = True
                unnamed_segment_count += 1

                osm_data = segment.get('osmData') or {}
                tags = osm_data.get('osm_tags')
                if isinstance(tags, dict) and tags:
                    key = tuple(sorted(tags.items()))
                    unnamed_tag_counter[key] += 1

        if run_has_unnamed_segments:
            runs_with_unnamed.append(run_record)

        if verbose:
            print(
                f'[run {run_number}] success '
                f'({source_vertex_id}->{target_vertex_id}) '
                f'distance={distance} time={time} '
                f'has_unnamed={run_has_unnamed_segments}'
            )

    return {
        'runs': runs,
        'successes': successes,
        'failures': failures,
        'unnamed_segment_count': unnamed_segment_count,
        'unnamed_tag_counter': unnamed_tag_counter,
        'runs_with_unnamed': runs_with_unnamed,
        'rng': rng,
    }


def print_summary(report: Dict[str, object], verbose: bool) -> None:
    runs = report['runs']
    successes = report['successes']
    failures = report['failures']
    unnamed_segment_count = report['unnamed_segment_count']
    unnamed_tag_counter: Counter[TagKey] = report['unnamed_tag_counter']  # type: ignore[assignment]
    runs_with_unnamed: Sequence[RunRecord] = report['runs_with_unnamed']  # type: ignore[assignment]
    rng: random.Random = report['rng']  # type: ignore[assignment]

    print('--- Fuzzing report ---')
    print(f'Runs attempted: {runs}')
    print(f'Successful routes: {successes}')
    print(f'Failed routes: {failures}')
    print(f'"Unnamed street" direction segments: {unnamed_segment_count}')

    print('\nTop "Unnamed street" tag sets:')
    if unnamed_tag_counter:
        for idx, (tag_key, count) in enumerate(
            unnamed_tag_counter.most_common(5),
            start=1,
        ):
            total_ways = count_chicago_ways_for_tag_key(tag_key)
            print(
                f'  {idx}. {format_tag_key(tag_key)} -> {count} segments '
                f'({total_ways} total chicago_ways with this tag set in db)'
            )
    else:
        print('  No unnamed segments with OSM tags were encountered.')

    if not runs_with_unnamed:
        print('\nNo successful routes with "Unnamed street" segments to display.')
        return
    if not verbose:
        print('\nRe-run with --verbose to see example routes containing "Unnamed street" segments.')
        return

    sample_size = min(3, len(runs_with_unnamed))
    sampled_runs = rng.sample(list(runs_with_unnamed), sample_size)

    print(f'\nSampled routes containing "Unnamed street" segments ({sample_size} shown):')
    for record in sampled_runs:
        print(
            f'Run {record.run_number}: '
            f'source={record.source_vertex_id}, '
            f'target={record.target_vertex_id}, '
            f'enable_v2={record.enable_v2}'
        )
        print(f'  Distance: {record.distance} | Time: {record.time}')

        for direction_index, direction in enumerate(record.directions, start=1):
            effective_name = direction.get('effectiveName') or '<unknown>'
            maneuver = direction.get('maneuver', 'Continue')
            distance_m = direction.get('distance', 0.0) or 0.0
            print(
                f'  Direction {direction_index}: '
                f'{maneuver} on {effective_name} ({distance_m:.1f} m)'
            )
            for segment in direction.get('directionSegments', []):
                seg_name = segment.get('name') or segment.get('effectiveName') or '<unnamed>'
                seg_distance = segment.get('distance', 0.0) or 0.0
                print(
                    f'    Segment #{segment.get("featureIndex")}: '
                    f'{seg_name} ({seg_distance:.1f} m)'
                )
                osm_tags = (segment.get('osmData') or {}).get('osm_tags') or {}
                print(f'      tags: {format_tags_dict(osm_tags)}')


def main() -> int:
    args = parse_args()
    rng = random.Random(args.seed)
    maybe_set_pg_seed(args.seed)
    report = fuzz_directions(
        runs=args.runs,
        enable_v2=args.enable_v2,
        rng=rng,
        verbose=args.verbose,
    )
    print_summary(report, args.verbose)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - surface unexpected errors
        print(f'Unexpected error: {exc}', file=sys.stderr)
        raise
