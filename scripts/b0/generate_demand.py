#!/usr/bin/env python3
"""Generate the one frozen, seeded B0 fixed-route demand file."""

from __future__ import annotations

import json
import random
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path


SEED = 20260904
BLOCK_COUNT = 15
BLOCK_SECONDS = 60
OFFSETS_SECONDS = tuple(range(0, 60, 5))
ROUTE_OUTPUT = Path("inputs/b0-fixed-routes.rou.xml")
MANIFEST_OUTPUT = Path("inputs/demand-manifest.json")

ROUTES = (
    ("row0_east", "left0A0 A0B0 B0C0 C0right0"),
    ("row0_west", "right0C0 C0B0 B0A0 A0left0"),
    ("row1_east", "left1A1 A1B1 B1C1 C1right1"),
    ("row1_west", "right1C1 C1B1 B1A1 A1left1"),
    ("row2_east", "left2A2 A2B2 B2C2 C2right2"),
    ("row2_west", "right2C2 C2B2 B2A2 A2left2"),
    ("colA_north", "bottom0A0 A0A1 A1A2 A2top0"),
    ("colA_south", "top0A2 A2A1 A1A0 A0bottom0"),
    ("colB_north", "bottom1B0 B0B1 B1B2 B2top1"),
    ("colB_south", "top1B2 B2B1 B1B0 B0bottom1"),
    ("colC_north", "bottom2C0 C0C1 C1C2 C2top2"),
    ("colC_south", "top2C2 C2C1 C1C0 C0bottom2"),
)


def main() -> None:
    if ROUTE_OUTPUT.exists() or MANIFEST_OUTPUT.exists():
        raise SystemExit("refusing to regenerate frozen B0 demand")
    if len(ROUTES) != len(OFFSETS_SECONDS):
        raise SystemExit("route/offset cardinality mismatch")

    rng = random.Random(SEED)
    scheduled: list[dict[str, object]] = []
    vehicle_index = 0

    root = ET.Element("routes")
    ET.SubElement(
        root,
        "vType",
        {
            "id": "passenger_deterministic",
            "vClass": "passenger",
            "accel": "2.6",
            "decel": "4.5",
            "sigma": "0",
            "length": "5.0",
            "minGap": "2.5",
            "maxSpeed": "13.89",
        },
    )
    for route_id, edges in ROUTES:
        ET.SubElement(root, "route", {"id": route_id, "edges": edges})

    for block in range(BLOCK_COUNT):
        block_routes = list(ROUTES)
        rng.shuffle(block_routes)
        for offset, (route_id, edges) in zip(OFFSETS_SECONDS, block_routes):
            vehicle_id = f"veh_{vehicle_index:04d}"
            depart = block * BLOCK_SECONDS + offset
            ET.SubElement(
                root,
                "vehicle",
                {
                    "id": vehicle_id,
                    "type": "passenger_deterministic",
                    "route": route_id,
                    "depart": str(depart),
                    "departLane": "best",
                    "departSpeed": "max",
                },
            )
            scheduled.append(
                {
                    "vehicle_id": vehicle_id,
                    "scheduled_departure_seconds": depart,
                    "route_id": route_id,
                    "edges": edges.split(),
                }
            )
            vehicle_index += 1

    ET.indent(root, space="  ")
    ET.ElementTree(root).write(ROUTE_OUTPUT, encoding="utf-8", xml_declaration=True)

    route_counts = Counter(str(item["route_id"]) for item in scheduled)
    manifest = {
        "scenario_seed": SEED,
        "generation_algorithm": "15 sixty-second blocks; one vehicle per explicit route per block; seeded route-to-five-second-offset permutation",
        "demand_window_seconds": {"start_inclusive": 0, "end_exclusive": 900},
        "scheduled_trip_count": len(scheduled),
        "route_count": len(ROUTES),
        "trips_per_route": dict(sorted(route_counts.items())),
        "routes_fixed_before_simulation": True,
        "dynamic_rerouting": False,
        "scheduled_trips": scheduled,
    }
    MANIFEST_OUTPUT.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
