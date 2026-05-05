#!/usr/bin/env python3
"""
Curriculum Generator — Merge parsed lessons with fleet competencies into a complete DAG.

Reads parsed_lessons.json and fleet_curriculum.json, then produces a unified
curriculum.json that matches the cocapn-curriculum module format.

Usage:
    python scripts/generate_curriculum.py \
        --lessons parsed_lessons.json \
        --competencies fleet_curriculum.json \
        --output curriculum.json

The generator:
1. Loads the competency DAG from fleet_curriculum.json
2. Injects lesson nodes from parsed lessons
3. Maps lessons to competencies (many-to-one)
4. Adds lesson-level prerequisite edges
5. Computes derived fields: total_xp, lesson_count per competency, etc.
6. Outputs curriculum.json with both competency and lesson graphs.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    """Load and return JSON from a file."""
    if not path.exists():
        print(f"Error: File not found: {path}", file=sys.stderr)
        sys.exit(1)
    return json.loads(path.read_text(encoding="utf-8"))


def merge_new_competencies(competencies: dict[str, Any], lessons: dict[str, Any]) -> dict[str, Any]:
    """Ensure every lesson competency exists in the competency map."""
    for lesson_id, lesson in lessons.items():
        comp_id = lesson.get("competency")
        if not comp_id:
            continue
        if comp_id not in competencies:
            # Derive a new competency from the lesson metadata
            competencies[comp_id] = {
                "id": comp_id,
                "name": lesson.get("title", comp_id).split("—")[0].strip(),
                "description": f"Competency derived from lesson {lesson_id}",
                "level": lesson.get("level", "Recruit"),
                "requires": [],
                "estimated_xp": lesson.get("estimated_xp", 500),
                "quests": [lesson.get("title", "Complete lesson")],
                "completion_rate": 0.0,
            }
            print(f"  + Added new competency: {comp_id}")
    return competencies


def link_lessons_to_competencies(lessons: dict[str, Any]) -> dict[str, list[str]]:
    """Build a map: competency_id -> [lesson_id, ...]."""
    mapping: dict[str, list[str]] = {}
    for lesson_id, lesson in lessons.items():
        comp_id = lesson.get("competency")
        if comp_id:
            mapping.setdefault(comp_id, []).append(lesson_id)
    return mapping


def build_lesson_graph(lessons: dict[str, Any]) -> dict[str, Any]:
    """Build the lesson DAG from prerequisite fields."""
    nodes = list(lessons.keys())
    edges = []

    for lesson_id, lesson in lessons.items():
        for prereq in lesson.get("prerequisites", []):
            if prereq in lessons:
                edges.append({
                    "from": prereq,
                    "to": lesson_id,
                    "type": "prerequisites"
                })
            else:
                print(f"  ⚠ Lesson {lesson_id} references unknown prerequisite: {prereq}")

    return {"nodes": nodes, "edges": edges}


def compute_lesson_order(lessons: dict[str, Any]) -> list[str]:
    """Topological sort of the lesson DAG (Kahn's algorithm)."""
    in_degree = {lid: 0 for lid in lessons}
    adj = {lid: [] for lid in lessons}

    for lesson_id, lesson in lessons.items():
        for prereq in lesson.get("prerequisites", []):
            if prereq in lessons:
                adj[prereq].append(lesson_id)
                in_degree[lesson_id] += 1

    queue = [lid for lid, deg in in_degree.items() if deg == 0]
    order = []

    while queue:
        node = queue.pop(0)
        order.append(node)
        for neighbor in adj[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(order) != len(lessons):
        remaining = set(lessons.keys()) - set(order)
        print(f"  ✗ Cycle detected in lesson graph! Remaining: {remaining}", file=sys.stderr)
        # Return what we have; validator will catch the full cycle
        order.extend(sorted(remaining))

    return order


def annotate_competencies(competencies: dict[str, Any], lessons: dict[str, Any], comp_to_lessons: dict[str, list[str]]) -> dict[str, Any]:
    """Add derived fields to competencies based on linked lessons."""
    for comp_id, comp in competencies.items():
        linked = comp_to_lessons.get(comp_id, [])
        comp["lesson_count"] = len(linked)
        # Sum XP from linked lessons if competency doesn't have its own
        if linked and comp.get("estimated_xp", 0) == 0:
            total = sum(lessons[lid].get("estimated_xp", 0) for lid in linked)
            comp["estimated_xp"] = total
        # Build learning path quests from lessons
        if linked:
            comp["lesson_quests"] = [f"Complete {lid}" for lid in linked]
    return competencies


def generate_curriculum(lessons_data: dict[str, Any], competencies_data: dict[str, Any]) -> dict[str, Any]:
    """Merge lessons and competencies into a unified curriculum structure."""
    lessons = lessons_data.get("lessons", {})

    # Start with competency framework
    competencies = dict(competencies_data.get("competencies", {}))
    levels = competencies_data.get("levels", ["Recruit", "Sailor", "Officer", "Captain", "Admiral"])
    xp_thresholds = competencies_data.get("xp_thresholds", {
        "Recruit": 0, "Sailor": 1000, "Officer": 5000, "Captain": 20000, "Admiral": 100000
    })

    # Ensure all lesson competencies exist
    print("Merging competencies from lessons...")
    competencies = merge_new_competencies(competencies, lessons)

    # Map competencies to lessons
    print("Linking lessons to competencies...")
    comp_to_lessons = link_lessons_to_competencies(lessons)

    # Annotate competencies with lesson metadata
    competencies = annotate_competencies(competencies, lessons, comp_to_lessons)

    # Build lesson DAG
    print("Building lesson graph...")
    lesson_graph = build_lesson_graph(lessons)
    lesson_order = compute_lesson_order(lessons)

    # Build lesson-to-competency edges (lessons unlock competencies)
    unlock_edges = []
    for comp_id, linked_lessons in comp_to_lessons.items():
        for lid in linked_lessons:
            unlock_edges.append({
                "from": lid,
                "to": comp_id,
                "type": "unlocks"
            })

    # Compute coverage statistics
    total_lesson_xp = sum(l.get("estimated_xp", 0) for l in lessons.values())
    competencies_with_lessons = sum(1 for c in competencies if comp_to_lessons.get(c))

    curriculum = {
        "schema_version": "1.0",
        "generated_at": None,  # filled below
        "levels": levels,
        "xp_thresholds": xp_thresholds,
        "competencies": competencies,
        "lessons": lessons,
        "competency_to_lessons": comp_to_lessons,
        "lesson_graph": lesson_graph,
        "lesson_order": lesson_order,
        "unlock_edges": unlock_edges,
        "statistics": {
            "total_lessons": len(lessons),
            "total_competencies": len(competencies),
            "competencies_with_lessons": competencies_with_lessons,
            "total_lesson_xp": total_lesson_xp,
            "lessons_without_competency": [lid for lid, l in lessons.items() if not l.get("competency")],
            "competencies_without_lessons": [cid for cid in competencies if cid not in comp_to_lessons],
        }
    }

    return curriculum


def main():
    parser = argparse.ArgumentParser(description="Generate unified curriculum from lessons and competencies.")
    parser.add_argument("--lessons", default="parsed_lessons.json", help="Parsed lessons JSON")
    parser.add_argument("--competencies", default="fleet_curriculum.json", help="Fleet competencies JSON")
    parser.add_argument("--output", default="curriculum.json", help="Output curriculum JSON")
    args = parser.parse_args()

    lessons_path = Path(args.lessons)
    competencies_path = Path(args.competencies)
    output_path = Path(args.output)

    print(f"Loading lessons from {lessons_path}...")
    lessons_data = load_json(lessons_path)

    print(f"Loading competencies from {competencies_path}...")
    competencies_data = load_json(competencies_path)

    print("Generating curriculum...")
    curriculum = generate_curriculum(lessons_data, competencies_data)

    # Add generation timestamp
    from datetime import datetime, timezone
    curriculum["generated_at"] = datetime.now(timezone.utc).isoformat()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(curriculum, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nWrote curriculum to {output_path}")
    print(f"  Lessons: {curriculum['statistics']['total_lessons']}")
    print(f"  Competencies: {curriculum['statistics']['total_competencies']}")
    print(f"  Competencies with lessons: {curriculum['statistics']['competencies_with_lessons']}")
    print(f"  Total lesson XP: {curriculum['statistics']['total_lesson_xp']}")

    if curriculum["statistics"]["lessons_without_competency"]:
        print(f"  ⚠ Lessons without competency: {curriculum['statistics']['lessons_without_competency']}")
    if curriculum["statistics"]["competencies_without_lessons"]:
        print(f"  ⚠ Competencies without lessons: {curriculum['statistics']['competencies_without_lessons']}")


if __name__ == "__main__":
    main()
