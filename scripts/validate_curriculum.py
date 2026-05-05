#!/usr/bin/env python3
"""
Curriculum Validator — Check the generated curriculum for structural integrity.

Validates:
1. All lesson prerequisites reference existing lessons
2. All competency prerequisites reference existing competencies
3. No cycles in the lesson DAG
4. No cycles in the competency DAG
5. All competencies have at least one lesson (coverage check)
6. All lessons map to a valid competency
7. XP totals are consistent
8. Reports coverage statistics

Usage:
    python scripts/validate_curriculum.py [--input curriculum.json] [--strict]

Exit codes:
    0 — all checks passed
    1 — one or more checks failed
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any


class ValidationResult:
    def __init__(self):
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.passed: list[str] = []

    def add_error(self, msg: str):
        self.errors.append(msg)

    def add_warning(self, msg: str):
        self.warnings.append(msg)

    def add_passed(self, msg: str):
        self.passed.append(msg)

    def summary(self) -> dict[str, Any]:
        return {
            "passed": len(self.passed),
            "warnings": len(self.warnings),
            "errors": len(self.errors),
            "details": {
                "passed": self.passed,
                "warnings": self.warnings,
                "errors": self.errors,
            },
        }


def load_curriculum(path: Path) -> dict[str, Any]:
    if not path.exists():
        print(f"Error: File not found: {path}", file=sys.stderr)
        sys.exit(1)
    return json.loads(path.read_text(encoding="utf-8"))


def check_lesson_prerequisites_exist(curriculum: dict[str, Any], result: ValidationResult):
    """Check 1: All lesson prerequisites reference existing lessons."""
    lessons = curriculum.get("lessons", {})
    missing = []
    for lesson_id, lesson in lessons.items():
        for prereq in lesson.get("prerequisites", []):
            if prereq not in lessons:
                missing.append(f"{lesson_id} -> {prereq}")
    if missing:
        result.add_error(f"Missing lesson prerequisites: {missing}")
    else:
        result.add_passed("All lesson prerequisites reference existing lessons")


def check_competency_prerequisites_exist(curriculum: dict[str, Any], result: ValidationResult):
    """Check 2: All competency prerequisites reference existing competencies."""
    competencies = curriculum.get("competencies", {})
    missing = []
    for comp_id, comp in competencies.items():
        for prereq in comp.get("requires", []):
            if prereq not in competencies:
                missing.append(f"{comp_id} -> {prereq}")
    if missing:
        result.add_error(f"Missing competency prerequisites: {missing}")
    else:
        result.add_passed("All competency prerequisites reference existing competencies")


def detect_cycles(nodes: list[str], edges: list[dict[str, str]]) -> list[list[str]]:
    """Detect all cycles in a DAG using DFS with coloring."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {n: WHITE for n in nodes}
    adj = {n: [] for n in nodes}
    for edge in edges:
        src, dst = edge.get("from"), edge.get("to")
        if src in adj and dst in adj:
            adj[src].append(dst)

    cycles = []
    path = []

    def dfs(node):
        color[node] = GRAY
        path.append(node)
        for neighbor in adj[node]:
            if color[neighbor] == GRAY:
                # Found cycle — extract it
                cycle_start = path.index(neighbor)
                cycle = path[cycle_start:] + [neighbor]
                cycles.append(cycle)
            elif color[neighbor] == WHITE:
                dfs(neighbor)
        path.pop()
        color[node] = BLACK

    for node in nodes:
        if color[node] == WHITE:
            dfs(node)

    return cycles


def check_lesson_dag_acyclic(curriculum: dict[str, Any], result: ValidationResult):
    """Check 3: No cycles in the lesson DAG."""
    lessons = curriculum.get("lessons", {})
    graph = curriculum.get("lesson_graph", {})
    nodes = graph.get("nodes", list(lessons.keys()))
    edges = graph.get("edges", [])

    cycles = detect_cycles(nodes, edges)
    if cycles:
        for cycle in cycles:
            result.add_error(f"Cycle in lesson DAG: {' -> '.join(cycle)}")
    else:
        result.add_passed("Lesson DAG is acyclic")


def check_competency_dag_acyclic(curriculum: dict[str, Any], result: ValidationResult):
    """Check 4: No cycles in the competency DAG."""
    competencies = curriculum.get("competencies", {})
    nodes = list(competencies.keys())
    edges = []
    for comp_id, comp in competencies.items():
        for prereq in comp.get("requires", []):
            edges.append({"from": prereq, "to": comp_id})

    cycles = detect_cycles(nodes, edges)
    if cycles:
        for cycle in cycles:
            result.add_error(f"Cycle in competency DAG: {' -> '.join(cycle)}")
    else:
        result.add_passed("Competency DAG is acyclic")


def check_competency_coverage(curriculum: dict[str, Any], result: ValidationResult, strict: bool = False):
    """Check 5: All competencies have at least one lesson (coverage)."""
    stats = curriculum.get("statistics", {})
    without_lessons = stats.get("competencies_without_lessons", [])
    if without_lessons:
        msg = f"Competencies without lessons ({len(without_lessons)}): {without_lessons}"
        if strict:
            result.add_error(msg)
        else:
            result.add_warning(msg)
    else:
        result.add_passed("All competencies have at least one linked lesson")


def check_lesson_competency_mapping(curriculum: dict[str, Any], result: ValidationResult):
    """Check 6: All lessons map to a valid competency."""
    lessons = curriculum.get("lessons", {})
    competencies = curriculum.get("competencies", {})
    unmapped = []
    for lesson_id, lesson in lessons.items():
        comp = lesson.get("competency")
        if not comp:
            unmapped.append(f"{lesson_id} (no competency)")
        elif comp not in competencies:
            unmapped.append(f"{lesson_id} -> {comp} (competency not found)")
    if unmapped:
        result.add_error(f"Unmapped lessons: {unmapped}")
    else:
        result.add_passed("All lessons map to valid competencies")


def check_xp_consistency(curriculum: dict[str, Any], result: ValidationResult):
    """Check 7: XP totals are consistent."""
    lessons = curriculum.get("lessons", {})
    competencies = curriculum.get("competencies", {})
    comp_to_lessons = curriculum.get("competency_to_lessons", {})

    inconsistencies = []
    for comp_id, comp in competencies.items():
        linked = comp_to_lessons.get(comp_id, [])
        if not linked:
            continue
        lesson_xp = sum(lessons[lid].get("estimated_xp", 0) for lid in linked)
        comp_xp = comp.get("estimated_xp", 0)
        if comp_xp != lesson_xp and comp_xp > 0:
            # Allow discrepancy if competency XP was manually set higher
            if lesson_xp > comp_xp:
                inconsistencies.append(
                    f"{comp_id}: competency XP={comp_xp} < lesson XP sum={lesson_xp}"
                )

    if inconsistencies:
        result.add_warning(f"XP inconsistencies: {inconsistencies}")
    else:
        result.add_passed("XP totals are consistent")


def check_level_validity(curriculum: dict[str, Any], result: ValidationResult):
    """Check 8: All levels referenced exist in the levels list."""
    levels = curriculum.get("levels", [])
    lessons = curriculum.get("lessons", {})
    competencies = curriculum.get("competencies", {})

    bad_lessons = [lid for lid, l in lessons.items() if l.get("level") not in levels]
    bad_comps = [cid for cid, c in competencies.items() if c.get("level") not in levels]

    if bad_lessons:
        result.add_error(f"Lessons with invalid levels: {bad_lessons}")
    if bad_comps:
        result.add_error(f"Competencies with invalid levels: {bad_comps}")
    if not bad_lessons and not bad_comps:
        result.add_passed("All levels are valid")


def report_statistics(curriculum: dict[str, Any], result: ValidationResult):
    """Print coverage and structural statistics."""
    stats = curriculum.get("statistics", {})
    lessons = curriculum.get("lessons", {})
    competencies = curriculum.get("competencies", {})
    levels = curriculum.get("levels", [])

    # Level distribution of lessons
    level_dist = {lvl: 0 for lvl in levels}
    for lesson in lessons.values():
        lvl = lesson.get("level")
        if lvl in level_dist:
            level_dist[lvl] += 1

    # Level distribution of competencies
    comp_level_dist = {lvl: 0 for lvl in levels}
    for comp in competencies.values():
        lvl = comp.get("level")
        if lvl in comp_level_dist:
            comp_level_dist[lvl] += 1

    coverage = stats.get("competencies_with_lessons", 0) / len(competencies) if competencies else 0

    print("\n=== Coverage Statistics ===")
    print(f"  Total lessons:        {len(lessons)}")
    print(f"  Total competencies:     {len(competencies)}")
    print(f"  Competency coverage:    {coverage:.1%}")
    print(f"  Total lesson XP:        {stats.get('total_lesson_xp', 0)}")
    print(f"\n  Lesson level distribution:")
    for lvl in levels:
        print(f"    {lvl:<10} {level_dist.get(lvl, 0)}")
    print(f"\n  Competency level distribution:")
    for lvl in levels:
        print(f"    {lvl:<10} {comp_level_dist.get(lvl, 0)}")


def main():
    parser = argparse.ArgumentParser(description="Validate Cocapn Fleet curriculum.")
    parser.add_argument("--input", default="curriculum.json", help="Curriculum JSON to validate")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    parser.add_argument("--output-report", help="Write validation report to JSON file")
    args = parser.parse_args()

    curriculum = load_curriculum(Path(args.input))
    result = ValidationResult()

    print(f"Validating curriculum: {args.input}")
    print(f"  Lessons:      {len(curriculum.get('lessons', {}))}")
    print(f"  Competencies: {len(curriculum.get('competencies', {}))}")
    print()

    check_lesson_prerequisites_exist(curriculum, result)
    check_competency_prerequisites_exist(curriculum, result)
    check_lesson_dag_acyclic(curriculum, result)
    check_competency_dag_acyclic(curriculum, result)
    check_competency_coverage(curriculum, result, strict=args.strict)
    check_lesson_competency_mapping(curriculum, result)
    check_xp_consistency(curriculum, result)
    check_level_validity(curriculum, result)

    report_statistics(curriculum, result)

    print("\n=== Validation Results ===")
    print(f"  Passed:   {len(result.passed)}")
    print(f"  Warnings: {len(result.warnings)}")
    print(f"  Errors:   {len(result.errors)}")

    if result.passed:
        print("\n  ✓ Passed:")
        for p in result.passed:
            print(f"      {p}")
    if result.warnings:
        print("\n  ⚠ Warnings:")
        for w in result.warnings:
            print(f"      {w}")
    if result.errors:
        print("\n  ✗ Errors:")
        for e in result.errors:
            print(f"      {e}")

    if args.output_report:
        report_path = Path(args.output_report)
        report_path.write_text(json.dumps(result.summary(), indent=2), encoding="utf-8")
        print(f"\nReport written to {report_path}")

    if result.errors or (args.strict and result.warnings):
        print("\nValidation FAILED")
        sys.exit(1)
    else:
        print("\nValidation PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
