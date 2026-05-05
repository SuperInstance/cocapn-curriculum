#!/usr/bin/env python3
"""
Lesson Parser — Extract structured data from Cocapn Fleet lesson markdown files.

Reads all .md files in the lessons/ directory, extracts metadata and pedagogical
content, and outputs a single JSON file with structured lesson records.

Usage:
    python scripts/parse_lessons.py [--lessons-dir lessons/] [--output parsed_lessons.json]

Output format:
    {
      "lessons": {
        "001-first-contact": {
          "id": "001-first-contact",
          "title": "First Contact — Making HTTP Requests with curl",
          "level": "Recruit",
          "competency": "http_curl",
          "estimated_xp": 100,
          "time": "10-15 minutes",
          "prerequisites": [],
          "learning_objectives": [...],
          "worked_example": {...},
          "trials": [...],
          "exercise": {...},
          "assessment": {...},
          "instructor_notes": "...",
          "metadata": {...}
        },
        ...
      }
    }
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


def parse_metadata(text: str) -> dict[str, Any]:
    """Extract metadata fields from the header block of a lesson."""
    meta = {}

    # Title from H1
    title_match = re.search(r"^#\s+Lesson\s+\d+:\s+(.+)$", text, re.MULTILINE)
    if title_match:
        meta["title"] = title_match.group(1).strip()

    # Level
    level_match = re.search(r"\*\*Level:\*\*\s*(\w+)", text)
    if level_match:
        meta["level"] = level_match.group(1).strip()

    # Competency
    comp_match = re.search(r"\*\*Competency:\*\*\s*`?([^`\n]+)`?", text)
    if comp_match:
        comp = comp_match.group(1).strip()
        # Strip parenthetical notes like "(partial — full mastery at Sailor)"
        comp = re.sub(r"\s*\(.*?\)", "", comp).strip()
        meta["competency"] = comp

    # Estimated XP
    xp_match = re.search(r"\*\*Estimated XP:\*\*\s*(\d+)", text)
    if xp_match:
        meta["estimated_xp"] = int(xp_match.group(1))

    # Time
    time_match = re.search(r"\*\*Time:\*\*\s*(.+?)$", text, re.MULTILINE)
    if time_match:
        meta["time"] = time_match.group(1).strip()

    # Prerequisites
    prereq_match = re.search(r"\*\*Prerequisites:\*\*\s*(.+?)$", text, re.MULTILINE)
    if prereq_match:
        prereq_text = prereq_match.group(1).strip()
        if prereq_text.lower() in ("none", "", "n/a"):
            meta["prerequisites"] = []
        else:
            meta["prerequisites"] = [p.strip() for p in prereq_text.split(",")]

    return meta


def extract_section(text: str, heading: str) -> str:
    """Extract the content under a markdown heading, up to the next heading of same or higher level."""
    pattern = re.compile(
        rf"^(##\s+{re.escape(heading)}.*?)$"
        r"(.*?)(?=^##\s|\Z)",
        re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )
    match = pattern.search(text)
    if match:
        return match.group(2).strip()
    return ""


def parse_learning_objectives(section: str) -> list[str]:
    """Parse numbered list items from the Learning Objectives section."""
    objectives = []
    for line in section.splitlines():
        line = line.strip()
        # Match "1. Do something" or "- Do something"
        m = re.match(r"^(?:\d+\.\s*|[-*]\s+)(.+)", line)
        if m:
            objectives.append(m.group(1).strip())
    return objectives


def parse_worked_example(section: str) -> dict[str, Any]:
    """Parse the Worked Example section into structured data."""
    result = {
        "scenario": "",
        "expert": "",
        "steps": [],
        "key_insight": "",
        "time_taken": "",
        "tokens_used": "",
    }

    # Scenario
    scenario_match = re.search(r"\*\*Scenario:\*\*\s*(.+?)(?=\n\n|\n\*\*|$)", section, re.DOTALL)
    if scenario_match:
        result["scenario"] = scenario_match.group(1).strip().replace("\n", " ")

    # Expert attribution
    expert_match = re.search(r"\*\*Expert solution\s*\((.+?)\):\*\*", section)
    if expert_match:
        result["expert"] = expert_match.group(1).strip()

    # Steps — capture code blocks with their preceding text
    steps = []
    # Find step descriptions and associated code blocks
    step_pattern = re.compile(
        r"^(#+\s*Step\s+\d+[:\.]?\s*(.+?))$"
        r"|^(Step\s+\d+[:\.]?\s*(.+?))$"
        r"|^(\*\*Step\s+\d+[:\.]?\s*(.+?)\*\*)$",
        re.MULTILINE | re.IGNORECASE,
    )

    # Simpler approach: split by code fences and collect narrative + code pairs
    parts = re.split(r"(```[\w]*\n.*?```)", section, flags=re.DOTALL)
    current_desc = ""
    for part in parts:
        part = part.strip()
        if part.startswith("```"):
            lang_match = re.match(r"```(\w+)?", part)
            lang = lang_match.group(1) if lang_match else ""
            code = re.sub(r"^```[\w]*\n", "", part)
            code = re.sub(r"\n```$", "", code)
            steps.append({"description": current_desc, "language": lang, "code": code})
            current_desc = ""
        else:
            # Extract any step labels
            step_label_match = re.search(r"Step\s+\d+[:\.]?\s*(.+?)$", part, re.MULTILINE | re.IGNORECASE)
            if step_label_match:
                current_desc = step_label_match.group(1).strip()
            elif part and not part.startswith("**"):
                # Use non-bold, non-empty text as description
                lines = [l.strip() for l in part.splitlines() if l.strip() and not l.strip().startswith("**")]
                if lines:
                    current_desc = " ".join(lines)

    if steps:
        result["steps"] = steps

    # Key insight
    insight_match = re.search(r"\*\*Key insight:\*\*\s*(.+?)(?=\n\n|\n\*\*|$)", section, re.DOTALL)
    if insight_match:
        result["key_insight"] = insight_match.group(1).strip().replace("\n", " ")

    # Time taken
    time_match = re.search(r"\*\*Time taken:\*\*\s*(.+?)$", section, re.MULTILINE)
    if time_match:
        result["time_taken"] = time_match.group(1).strip()

    # Tokens used
    tokens_match = re.search(r"\*\*Tokens used:\*\*\s*(.+?)$", section, re.MULTILINE)
    if tokens_match:
        result["tokens_used"] = tokens_match.group(1).strip()

    return result


def parse_trials(section: str) -> list[dict[str, Any]]:
    """Parse Common Failures (Trials) section into structured trial records."""
    trials = []
    # Each trial is a ### heading followed by content
    trial_pattern = re.compile(
        r"^###\s+(Trial\s+\w+[:\.]?\s*(.*?))$"
        r"(.*?)(?=^###\s|\Z)",
        re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )

    for match in trial_pattern.finditer(section):
        title = match.group(2).strip() if match.group(2) else match.group(1).strip()
        body = match.group(3).strip()

        trial = {
            "id": re.search(r"Trial\s+(\w+)", match.group(1)).group(1) if re.search(r"Trial\s+(\w+)", match.group(1)) else "",
            "title": title,
            "code": "",
            "problem": "",
            "fix": "",
        }

        # Extract code block
        code_match = re.search(r"```[\w]*\n(.*?)```", body, re.DOTALL)
        if code_match:
            trial["code"] = code_match.group(1).strip()

        # Extract problem and fix
        problem_match = re.search(r"#?\s*Problem:\s*(.+?)(?=\n#?\s*Fix:|$)", body, re.DOTALL | re.IGNORECASE)
        if problem_match:
            trial["problem"] = problem_match.group(1).strip().replace("\n", " ")

        fix_match = re.search(r"#?\s*Fix:\s*(.+?)$", body, re.DOTALL | re.IGNORECASE)
        if fix_match:
            trial["fix"] = fix_match.group(1).strip().replace("\n", " ")

        trials.append(trial)

    return trials


def parse_exercise(section: str) -> dict[str, Any]:
    """Parse the Exercise section into structured data."""
    result = {
        "task": "",
        "scaffolding": {},
        "auto_adjust": False,
    }

    # Task
    task_match = re.search(r"\*\*Task:\*\*\s*(.+?)(?=\n\n|\n\*\*|$)", section, re.DOTALL)
    if task_match:
        result["task"] = task_match.group(1).strip().replace("\n", " ")

    # Scaffolding levels
    level_pattern = re.compile(
        r"^#+\s*Level\s+(\d+)\s*\((.+?)\)\s*[-—]\s*(.*?)$"
        r"(.*?)(?=^#+\s*Level\s+\d+|^\*\*Auto-adjust|\Z)",
        re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )

    for match in level_pattern.finditer(section):
        level_num = match.group(1)
        support = match.group(2).strip()
        desc = match.group(3).strip()
        body = match.group(4).strip()

        code_blocks = []
        for code_match in re.finditer(r"```[\w]*\n(.*?)```", body, re.DOTALL):
            code_blocks.append(code_match.group(1).strip())

        result["scaffolding"][f"level_{level_num}"] = {
            "support": support,
            "description": desc,
            "code_blocks": code_blocks,
        }

    # Auto-adjust
    auto_match = re.search(r"\*\*Auto-adjust:\*\*\s*(.+?)$", section, re.MULTILINE | re.IGNORECASE)
    if auto_match:
        val = auto_match.group(1).strip().lower()
        result["auto_adjust"] = val in ("true", "yes", "if you complete")

    return result


def parse_assessment(section: str) -> dict[str, Any]:
    """Parse the Assessment section into structured data."""
    result = {
        "pass_criteria": [],
        "verification": "",
        "retry_allowed": False,
        "max_retries": 0,
        "on_pass": {},
    }

    # Pass criteria — numbered list after "Pass criteria:"
    criteria_section = re.search(r"\*\*Pass criteria:\*\*(.*?)(?=\*\*Verification|\*\*Retry|\Z)", section, re.DOTALL | re.IGNORECASE)
    if criteria_section:
        criteria_text = criteria_section.group(1)
        for line in criteria_text.splitlines():
            line = line.strip()
            m = re.match(r"^(?:\d+\.\s*|[-*]\s+)(.+)", line)
            if m:
                result["pass_criteria"].append(m.group(1).strip())

    # Verification
    verif_match = re.search(r"\*\*Verification:\*\*\s*(.*?)(?=\*\*Retry|\*\*On pass|\Z)", section, re.DOTALL | re.IGNORECASE)
    if verif_match:
        result["verification"] = verif_match.group(1).strip()

    # Retry
    retry_match = re.search(r"\*\*Retry allowed:\*\*\s*(\w+)(?:\s*\(max\s*(\d+)\s*attempts\))?$", section, re.MULTILINE | re.IGNORECASE)
    if retry_match:
        result["retry_allowed"] = retry_match.group(1).lower() in ("yes", "true")
        if retry_match.group(2):
            result["max_retries"] = int(retry_match.group(2))

    # On pass
    on_pass_match = re.search(r"\*\*On pass:\*\*(.*?)$", section, re.DOTALL | re.IGNORECASE)
    if on_pass_match:
        on_pass_text = on_pass_match.group(1).strip()
        # Unlock competencies
        unlock_match = re.search(r"Unlock\s*`?([^`\n]+)`?", on_pass_text, re.IGNORECASE)
        if unlock_match:
            result["on_pass"]["unlock_competency"] = unlock_match.group(1).strip()
        # Level up
        level_match = re.search(r"advance\s+toward\s+(\w+)|level_up\s*[:=]\s*[\"']?(\w+)", on_pass_text, re.IGNORECASE)
        if level_match:
            result["on_pass"]["advance_to"] = level_match.group(1) or level_match.group(2)

    return result


def parse_instructor_notes(section: str) -> dict[str, Any]:
    """Parse Instructor Notes section."""
    result = {
        "stumbling_blocks": [],
        "teaching_strategy": [],
    }

    # Stumbling blocks
    blocks_match = re.search(r"\*\*Common stumbling blocks:\*\*(.*?)(?=\*\*Teaching strategy|\Z)", section, re.DOTALL | re.IGNORECASE)
    if blocks_match:
        for line in blocks_match.group(1).splitlines():
            line = line.strip()
            m = re.match(r"^(?:\d+\.\s*|[-*]\s+)(.+)", line)
            if m:
                result["stumbling_blocks"].append(m.group(1).strip())

    # Teaching strategy
    strategy_match = re.search(r"\*\*Teaching strategy:\*\*(.*?)$", section, re.DOTALL | re.IGNORECASE)
    if strategy_match:
        for line in strategy_match.group(1).splitlines():
            line = line.strip()
            m = re.match(r"^(?:\d+\.\s*|[-*]\s+)(.+)", line)
            if m:
                result["teaching_strategy"].append(m.group(1).strip())

    return result


def parse_lesson_file(path: Path) -> dict[str, Any]:
    """Parse a single lesson markdown file into a structured dictionary."""
    text = path.read_text(encoding="utf-8")
    lesson_id = path.stem

    lesson = {"id": lesson_id}
    lesson.update(parse_metadata(text))

    # Extract sections
    lesson["learning_objectives"] = parse_learning_objectives(extract_section(text, "Learning Objectives"))
    lesson["worked_example"] = parse_worked_example(extract_section(text, "Worked Example"))
    lesson["trials"] = parse_trials(extract_section(text, "Common Failures"))
    lesson["exercise"] = parse_exercise(extract_section(text, "Exercise"))
    lesson["assessment"] = parse_assessment(extract_section(text, "Assessment"))
    lesson["instructor_notes"] = parse_instructor_notes(extract_section(text, "Instructor Notes"))

    # Extract footer metadata
    footer = {}
    version_match = re.search(r"\*Lesson Version:\*\*\s*(.+?)$", text, re.MULTILINE)
    if version_match:
        footer["version"] = version_match.group(1).strip()

    author_match = re.search(r"\*Author:\*\*\s*(.+?)$", text, re.MULTILINE)
    if author_match:
        footer["author"] = author_match.group(1).strip()

    updated_match = re.search(r"\*Last Updated:\*\*\s*(.+?)$", text, re.MULTILINE)
    if updated_match:
        footer["last_updated"] = updated_match.group(1).strip()

    trials_count_match = re.search(r"\*Trials Contributed:\*\*\s*(\d+)", text)
    if trials_count_match:
        footer["trials_contributed"] = int(trials_count_match.group(1))

    avg_time_match = re.search(r"\*Average Completion Time:\*\*\s*(.+?)$", text, re.MULTILINE)
    if avg_time_match:
        footer["average_completion_time"] = avg_time_match.group(1).strip()

    success_rate_match = re.search(r"\*Success Rate:\*\*\s*(\d+)%", text)
    if success_rate_match:
        footer["success_rate"] = int(success_rate_match.group(1)) / 100.0

    lesson["metadata"] = footer

    return lesson


def main():
    parser = argparse.ArgumentParser(description="Parse Cocapn Fleet lesson markdown files.")
    parser.add_argument("--lessons-dir", default="lessons", help="Directory containing .md lesson files")
    parser.add_argument("--output", default="parsed_lessons.json", help="Output JSON file path")
    args = parser.parse_args()

    lessons_dir = Path(args.lessons_dir)
    if not lessons_dir.is_dir():
        print(f"Error: Directory not found: {lessons_dir}", file=sys.stderr)
        sys.exit(1)

    md_files = sorted(lessons_dir.glob("*.md"))
    if not md_files:
        print(f"Warning: No .md files found in {lessons_dir}", file=sys.stderr)

    lessons = {}
    for md_file in md_files:
        try:
            lesson = parse_lesson_file(md_file)
            lessons[lesson["id"]] = lesson
            print(f"  ✓ Parsed {lesson['id']}: {lesson.get('title', 'untitled')}")
        except Exception as e:
            print(f"  ✗ Failed to parse {md_file.name}: {e}", file=sys.stderr)

    output = {"lessons": lessons, "count": len(lessons)}

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nWrote {len(lessons)} lessons to {out_path}")


if __name__ == "__main__":
    main()
