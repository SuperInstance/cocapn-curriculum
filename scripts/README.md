# Cocapn Fleet Curriculum Scripts

Tools for integrating lesson markdown files into the cocapn-curriculum system.

## Pipeline

```
lessons/*.md  ──▶  parse_lessons.py  ──▶  parsed_lessons.json
                                            │
fleet_curriculum.json  ──────────────────────┤
                                            ▼
                                    generate_curriculum.py
                                            │
                                            ▼
                                    curriculum.json
                                            │
                                            ▼
                                    validate_curriculum.py
```

## Scripts

### 1. `parse_lessons.py`

Reads all `.md` files in `lessons/` and extracts structured data.

**Usage:**
```bash
python scripts/parse_lessons.py --lessons-dir lessons/ --output parsed_lessons.json
```

**Extracts:**
- Metadata: title, level, competency, estimated_xp, time, prerequisites
- Learning Objectives (numbered list)
- Worked Example (scenario, expert, steps, key insight, time, tokens)
- Trials (Common Failures — code, problem, fix)
- Exercise (task, scaffolding levels 1-3, auto-adjust)
- Assessment (pass criteria, verification, retry policy, on_pass rewards)
- Instructor Notes (stumbling blocks, teaching strategy)
- Footer metadata (version, author, last_updated, trials_count, success_rate)

### 2. `generate_curriculum.py`

Merges parsed lessons with `fleet_curriculum.json` into a unified curriculum DAG.

**Usage:**
```bash
python scripts/generate_curriculum.py \
    --lessons parsed_lessons.json \
    --competencies fleet_curriculum.json \
    --output curriculum.json
```

**What it does:**
- Ensures every lesson competency exists in the competency map
- Maps competencies → lessons (many-to-one)
- Builds the lesson prerequisite DAG
- Computes topological ordering of lessons
- Adds unlock edges (lessons → competencies)
- Annotates competencies with lesson counts and derived XP
- Reports coverage statistics

**Output format:** Compatible with `cocapn_curriculum.Curriculum.load()` plus a `lessons` field and `lesson_graph`.

### 3. `validate_curriculum.py`

Structural integrity checker for the generated curriculum.

**Usage:**
```bash
python scripts/validate_curriculum.py --input curriculum.json [--strict]
```

**Checks:**
1. All lesson prerequisites reference existing lessons
2. All competency prerequisites reference existing competencies
3. No cycles in the lesson DAG
4. No cycles in the competency DAG
5. All competencies have at least one lesson (warning unless `--strict`)
6. All lessons map to a valid competency
7. XP totals are consistent
8. All levels are valid

**Exit codes:**
- `0` — all checks passed
- `1` — one or more checks failed

## Quick Start

```bash
# Make scripts executable
chmod +x scripts/*.py

# Run the full pipeline
python scripts/parse_lessons.py
python scripts/generate_curriculum.py
python scripts/validate_curriculum.py

# Or one-liner:
python scripts/parse_lessons.py && \
  python scripts/generate_curriculum.py && \
  python scripts/validate_curriculum.py
```

## Files

| File | Description |
|------|-------------|
| `lessons/001-first-contact.md` | Recruit — curl HTTP requests |
| `lessons/002-room-mapping.md` | Recruit — MUD exploration |
| `lessons/003-tile-submission.md` | Recruit — PLATO tile submission |
| `lessons/004-guard-fundamentals.md` | Sailor — GUARD constraint compilation |
| `lessons/005-ci-deployment.md` | Sailor — GitHub Actions CI |
| `lessons/006-bottle-writing.md` | Sailor — Fleet bottle protocol |
| `lessons/007-subagent-orchestration.md` | Officer — Parallel fleet operations |
| `lessons/008-cross-linking.md` | Officer — Fleet resource linking |
| `lessons/009-security-auditing.md` | Officer — Security auditing |
| `fleet_curriculum.json` | Competency DAG (levels, XP thresholds, prerequisites) |
| `parsed_lessons.json` | Intermediate: structured lesson data |
| `curriculum.json` | Final output: unified curriculum |

## Integration with cocapn-curriculum

The generated `curriculum.json` can be loaded by the Python module:

```python
from cocapn_curriculum import Curriculum

cv = Curriculum.load("curriculum.json")
# Lessons are accessible via cv.data["lessons"]
# Lesson graph: cv.data["lesson_graph"]
# Competency → lessons: cv.data["competency_to_lessons"]
```

## Extending

To add a new lesson:
1. Write `lessons/007-your-lesson.md` following the existing template
2. Ensure the `Competency:` field matches an entry in `fleet_curriculum.json`
3. Re-run the pipeline

To add a new competency:
1. Add it to `fleet_curriculum.json` with `id`, `name`, `level`, `requires`, `estimated_xp`
2. Write a lesson that maps to it
3. Re-run the pipeline
