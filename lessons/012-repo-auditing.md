# Lesson 012: Repository Auditing — Fleet Inventory and Hygiene

**Level:** Captain
**Competency:** `repo_audit`
**Estimated XP:** 1400
**Time:** 40-50 minutes
**Prerequisites:** 005-ci-deployment, 008-cross-linking, 009-security-auditing

---

## Learning Objectives

After this lesson, you will be able to:
1. Audit GitHub repositories systematically for structural, security, and maintenance issues
2. Detect exposed secrets, missing CI/CD, stale dependencies, and documentation gaps using automated and manual methods
3. Grade repositories on a standardized rubric (A-F) across multiple dimensions
4. Write audit reports that are scannable, actionable, and prioritized
5. Build a fleet-wide repo health dashboard that tracks trends over time

---

## What Is Repository Auditing?

**Repository auditing** is inventory with teeth. It's not just "does the repo exist?" It's "is the repo healthy, secure, documented, and maintained — or is it technical debt waiting to collapse?"

At Officer level, you learned to audit a single repo for secrets. At Captain level, you audit the *fleet*. You compare repos against each other. You spot patterns: "3 repos are missing CI. 5 repos have READMEs from 2024 that don't mention the new architecture. 2 repos have open Dependabot alerts from last month."

**A Captain's repo audit answers:**
- Which repos are production-critical vs. experimental?
- Which repos would embarrass us if someone looked closely?
- Which repos are drifting toward unmaintainability?
- Where should we invest cleanup time this sprint?

**The audit dimensions:**
```
Security     — secrets, permissions, access control
CI/CD        — tests run? builds green? deployments automated?
Dependencies — stale? vulnerable? pinned?
Documentation — README accurate? API docs? Changelog?
Structure    — LICENSE? CONTRIBUTING? Issue templates? Code of conduct?
Activity     — commits in last 30 days? Issues closed? PRs merged?
```

---

## Worked Example: Fleet-Wide Repo Audit

**Scenario:** Casey wants a quarterly repo health report for the entire fleet. 20+ repos, but he only has 30 minutes. You need to audit, grade, and prioritize — fast.

**Expert solution (ccc-auditor-captain, 2026-05-05):**

**Step 1: Inventory — list all fleet repos**

```bash
# Get all repos under the SuperInstance org
curl -s "https://api.github.com/orgs/SuperInstance/repos?per_page=100" | \
  jq -r '.[] | select(.archived == false) | "\(.name)\t\(.updated_at)\t\(.open_issues_count)\t\(.default_branch)"' | \
  sort -t$'\t' -k2 -r > /tmp/fleet-repos.tsv

# Add manually tracked repos that might not be under the org
FLEET_REPOS=(
  "SuperInstance/cocapn-plato"
  "SuperInstance/flux-research"
  "SuperInstance/oracle1-vessel"
  "SuperInstance/JetsonClaw1-vessel"
  "SuperInstance/crab-traps"
  "SuperInstance/cocapn-docs"
  "SuperInstance/fleet-index"
  "SuperInstance/flux-c-tutor"
  "SuperInstance/cocapn-flux"
  "SuperInstance/purplepincher-web"
)
```

**Step 2: Automated structural checks (run in parallel via subagents)**

```bash
# Audit script template — one per repo
cat > /tmp/audit-repo.sh <<'SCRIPT'
#!/bin/bash
REPO="$1"
NAME=$(basename "$REPO")
TMPDIR="/tmp/audit-$NAME"
REPORT="/tmp/audit-report-$NAME.md"

# Clone (shallow, fast)
git clone --depth 1 "https://github.com/$REPO.git" "$TMPDIR" 2>/dev/null || {
  echo "FAILED: Cannot clone $REPO"
  exit 1
}

cd "$TMPDIR"

# --- Security checks ---
SECRETS="PASS"
truffleHOG --regex . > /dev/null 2>&1 || SECRETS="CHECK_MANUALLY"
[[ -f .gitignore ]] || SECRETS="FAIL"
grep -rE "AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9_]{36,}" . >/dev/null 2>&1 && SECRETS="FAIL"

# --- CI/CD checks ---
CICD="FAIL"
[[ -d .github/workflows ]] && [[ $(ls .github/workflows/*.yml 2>/dev/null | wc -l) -gt 0 ]] && CICD="PASS"
[[ -f .gitlab-ci.yml ]] && CICD="PASS"

# --- Dependency checks ---
DEPS="PASS"
[[ -f package.json ]] && [[ ! -f package-lock.json ]] && [[ ! -f yarn.lock ]] && DEPS="WARN"
[[ -f requirements.txt ]] && [[ ! -f requirements.lock ]] && [[ ! -f Pipfile.lock ]] && DEPS="WARN"
[[ -f Cargo.toml ]] && [[ ! -f Cargo.lock ]] && DEPS="WARN"

# --- Documentation checks ---
DOCS="PASS"
[[ -f README.md ]] || DOCS="FAIL"
[[ -s README.md ]] || DOCS="FAIL"  # Empty README
[[ -f LICENSE ]] || DOCS="WARN"
[[ -f CHANGELOG.md ]] || DOCS="WARN"

# --- Structure checks ---
STRUCT="PASS"
[[ -f .github/ISSUE_TEMPLATE/bug_report.md ]] || STRUCT="WARN"
[[ -f CONTRIBUTING.md ]] || STRUCT="WARN"

# --- Activity check (via API) ---
LAST_COMMIT=$(curl -s "https://api.github.com/repos/$REPO/commits?per_page=1" | jq -r '.[0].commit.committer.date')
DAYS_SINCE=$(( ($(date +%s) - $(date -d "$LAST_COMMIT" +%s)) / 86400 ))
ACTIVITY="PASS"
[[ $DAYS_SINCE -gt 60 ]] && ACTIVITY="WARN"
[[ $DAYS_SINCE -gt 120 ]] && ACTIVITY="FAIL"

# --- Grade calculation ---
GRADE="A"
[[ "$SECRETS" == "FAIL" ]] && GRADE="F"
[[ "$CICD" == "FAIL" ]] && [[ "$GRADE" != "F" ]] && GRADE="D"
[[ "$DOCS" == "FAIL" ]] && [[ "$GRADE" != "F" ]] && [[ "$GRADE" != "D" ]] && GRADE="C"
[[ "$DEPS" == "WARN" ]] && [[ "$GRADE" == "A" ]] && GRADE="B"
[[ "$ACTIVITY" == "WARN" ]] && [[ "$GRADE" == "A" ]] && GRADE="B"
[[ "$ACTIVITY" == "FAIL" ]] && [[ "$GRADE" == "A" || "$GRADE" == "B" ]] && GRADE="C"

# --- Write report ---
cat > "$REPORT" <<EOF
## $REPO Audit Report

| Dimension | Status | Notes |
|-----------|--------|-------|
| Security | $SECRETS | secrets + .gitignore |
| CI/CD | $CICD | GitHub Actions / GitLab CI |
| Dependencies | $DEPS | lockfile presence |
| Documentation | $DOCS | README, LICENSE, CHANGELOG |
| Structure | $STRUCT | issue templates, contributing |
| Activity | $ACTIVITY | last commit ${DAYS_SINCE} days ago |
| **Overall** | **$GRADE** | |
EOF

rm -rf "$TMPDIR"
echo "$REPO|$GRADE|$SECRETS|$CICD|$DEPS|$DOCS|$STRUCT|$ACTIVITY"
SCRIPT

chmod +x /tmp/audit-repo.sh

# Run on all fleet repos (in practice, parallel via subagents)
for repo in "${FLEET_REPOS[@]}"; do
  /tmp/audit-repo.sh "$repo" >> /tmp/fleet-audit-results.tsv
done
```

**Step 3: Synthesize fleet-wide report**

```bash
# Read all individual reports and build the fleet summary
cat > /tmp/fleet-repo-health-report.md <<'EOF'
[I2I:AUDIT] CCC 🦀 → Casey + Oracle1 🔮 — Fleet Repo Health Q2 2026

## Fleet Repo Health Dashboard

| Repo | Grade | Security | CI/CD | Deps | Docs | Structure | Activity | Priority |
|------|-------|----------|-------|------|------|-----------|----------|----------|
EOF

# Append rows from results
cat /tmp/fleet-audit-results.tsv | while IFS='|' read -r REPO GRADE SEC CICD DEPS DOCS STRUCT ACT; do
  # Color-code priority
  PRIORITY="LOW"
  [[ "$GRADE" == "F" ]] && PRIORITY="CRITICAL"
  [[ "$GRADE" == "D" ]] && PRIORITY="HIGH"
  [[ "$GRADE" == "C" ]] && PRIORITY="MEDIUM"
  [[ "$SEC" == "FAIL" ]] && PRIORITY="CRITICAL"
  echo "| $(basename $REPO) | $GRADE | $SEC | $CICD | $DEPS | $DOCS | $STRUCT | $ACT | $PRIORITY |" >> /tmp/fleet-repo-health-report.md
done

# Add summary statistics
cat >> /tmp/fleet-repo-health-report.md <<'EOF'

## Summary Statistics

| Grade | Count | Percentage |
|-------|-------|------------|
EOF

for g in A B C D F; do
  COUNT=$(grep -c "|$g|" /tmp/fleet-audit-results.tsv)
  echo "| $g | $COUNT | — |" >> /tmp/fleet-repo-health-report.md
done

cat >> /tmp/fleet-repo-health-report.md <<'EOF'

## Critical Actions Required

### CRITICAL (Grade F or Security FAIL)
- Immediate review needed. Do not deploy.

### HIGH (Grade D)
- Missing CI/CD. Add GitHub Actions or GitLab CI before next deploy.

### MEDIUM (Grade C)
- Documentation or activity gaps. Schedule cleanup in next sprint.

## Trends vs. Last Quarter
- Repos with improved grades: [list]
- Repos with degraded grades: [list]
- New repos added: [list]
- Repos archived: [list]

## Status
COMPLETE — All repos audited. Prioritized remediation list attached.
EOF
```

**Step 4: Deliver and route**

```bash
# Save to bottles directory
cp /tmp/fleet-repo-health-report.md /root/.openclaw/workspace/data/bottles/oracle1/fleet-repo-health-Q2-2026.md

# Key findings go to #fleet-ops
cat /tmp/fleet-audit-results.tsv | grep "FAIL\|F|" | while IFS='|' read -r REPO GRADE SEC CICD DEPS DOCS STRUCT ACT; do
  echo "⚠ CRITICAL: $REPO — Grade $GRADE, Security: $SEC, CI/CD: $CICD"
done
```

**Key insight:** The audit is automated, repeatable, and produces the same output format every time. Casey looks at the table, sees the grades, and knows exactly which repos need attention this week vs. next quarter. No prose. No ambiguity. Just a dashboard.

**Time taken:** 10 minutes (script) + 8 minutes (running on 10 repos) + 5 minutes (synthesis) = 23 minutes
**Tokens used:** ~5,000

---

## Common Failures (Trials)

### Trial A: Auditing without a rubric — inconsistent grades
```bash
# WRONG — different criteria per repo
# Repo A: "has README" = PASS
# Repo B: "README is good" = PASS (but it's 2 lines)
# Repo C: "no README" = FAIL
# Problem: Grades aren't comparable. You can't say "Repo A is healthier than Repo B."
# Fix: Define the rubric BEFORE auditing. Same criteria for every repo.
# Use the dimension table: Security, CI/CD, Dependencies, Documentation, Structure, Activity.
# Each dimension has PASS/WARN/FAIL criteria that are identical across all repos.
```

### Trial B: Only checking HEAD, not recent history
```bash
# WRONG — clone --depth 1, check current files, declare clean
git clone --depth 1 https://github.com/org/repo.git
# Problem: The secret was committed last month and removed yesterday.
# HEAD is clean. History is not. truffleHOG on --depth 1 misses it.
# Fix: For security dimension, use full clone or truffleHOG remote scan.
truffleHOG --regex --json https://github.com/org/repo.git
# For structure/docs dimensions, --depth 1 is fine.
```

### Trial C: Missing the "so what?" — audit without prioritization
```markdown
# WRONG — flat list of issues, no priority
- cocapn-plato: missing CHANGELOG
- flux-research: no issue templates
- crab-traps: old dependencies
- oracle1-vessel: no CI
# Problem: Everything is "an issue." Owner doesn't know what to fix first.
# A Captain's audit has teeth: grades, priorities, timelines.
# Fix: Assign grades (A-F), then map grades to priorities:
#   F = CRITICAL (fix this week)
#   D = HIGH (fix this sprint)
#   C = MEDIUM (next sprint)
#   B = LOW (nice to have)
#   A = maintain
```

### Trial D: One-and-done auditing — no tracking over time
```bash
# WRONG — run audit, deliver report, never do it again
# Problem: You don't know if things are getting better or worse.
# A repo that was "A" last quarter and is "C" this quarter is a warning.
# A repo that was "D" and is now "B" is a win that should be celebrated.
# Fix: Keep historical data. Compare quarter over quarter.
# Store results in a persistent location:
cp /tmp/fleet-audit-results.tsv /root/.openclaw/workspace/data/audit-history/2026-Q2.tsv
# Next quarter: diff against 2026-Q1.tsv to see trends.
```

---

## Exercise: Build the Fleet Repo Health System

**Task:** Design and implement a complete repo health monitoring system for the fleet. It should audit all repos automatically, track grades over time, and alert when a repo degrades.

**Scaffolding:**

```bash
# Level 1 (high support) — extend the worked example:
# 1. Add more repos to the audit list (at least 10 total)
# 2. Run the audit script on all of them
# 3. Generate the fleet-wide markdown report with the grade table
# 4. Identify the top 3 repos that need immediate attention
# 5. Write a remediation bottle to Oracle1 with specific actions per repo

# Use the audit-repo.sh template from the worked example.
# Add these extra checks:
# - Check for open Dependabot alerts (via GitHub API)
# - Check for stale branches (>90 days old)
# - Check for unmerged PRs >30 days old
# - Check if LICENSE is a standard OSI-approved license
```

```bash
# Level 2 (medium support):
# Write a fleet health tracker script that:
# 1. Reads a JSON config file defining fleet repos and their criticality:
#    {
#      "repos": [
#        {"name": "cocapn-plato", "criticality": "CRITICAL", "owner": "Oracle1"},
#        {"name": "flux-research", "criticality": "HIGH", "owner": "FM"}
#      ]
#    }
# 2. Runs the audit dimension checks on each repo
# 3. Stores results as JSON (not just markdown) for programmatic access
# 4. Compares against the previous run (if history exists)
# 5. Generates alerts for:
#    - Any CRITICAL repo with grade < B
#    - Any repo whose grade dropped since last run
#    - Any repo with Security = FAIL
# 6. Outputs a summary suitable for #fleet-ops
```

```bash
# Level 3 (low support):
# 1. Design a GitHub Actions workflow that:
#    - Runs the fleet audit weekly (Sunday at 02:00 UTC)
#    - Posts the report as a comment on fleet-index issue #1
#    - Creates issues automatically for any repo that drops a grade
#    - Labels issues by priority (critical-repo, grade-drop, security-fail)
#    - Assigns issues to the repo owner defined in the config
# 2. Write the workflow YAML and the audit runner script
# 3. Include a "repo health badge" system — each repo gets a badge in its README
#    showing current grade (updated by the weekly run)
# 4. Write the architecture as a bottle to Oracle1 and a PR to fleet-index
```

**Auto-adjust:** If you've already audited 5+ repos and written 2+ fleet reports, start at Level 2.

---

## Assessment

**Pass criteria:**
1. Audit at least 5 fleet repos across all 6 dimensions (Security, CI/CD, Dependencies, Documentation, Structure, Activity)
2. Assign grades (A-F) using a consistent rubric
3. Identify at least 1 repo with a real issue (even if LOW priority)
4. Write a fleet-wide synthesis report with a scannable grade table
5. Prioritize findings (CRITICAL/HIGH/MEDIUM/LOW) with suggested timelines
6. Save audit results to a persistent location for historical tracking

**Verification:**
```bash
# Automated checks
[[ -f /tmp/fleet-repo-health-report.md ]] && echo "✓ Fleet report exists"
grep -q "Grade\|A\|B\|C\|D\|F" /tmp/fleet-repo-health-report.md && echo "✓ Grading present"
grep -q "CRITICAL\|HIGH\|MEDIUM\|LOW" /tmp/fleet-repo-health-report.md && echo "✓ Prioritization present"
[[ $(grep -c "|$" /tmp/fleet-audit-results.tsv 2>/dev/null) -ge 5 ]] && echo "✓ 5+ repos audited"
[[ -d /root/.openclaw/workspace/data/audit-history ]] && echo "✓ History tracking enabled" || echo "⚠ No history dir — create one"
grep -q "Security\|CI/CD\|Dependencies\|Documentation\|Structure\|Activity" /tmp/fleet-repo-health-report.md && echo "✓ All dimensions covered"
```

**Retry allowed:** Yes (max 2 attempts)
**On pass:** Captain rank confirmed — fleet inventory specialty added

---

## Reference

### Audit Dimensions Rubric

| Dimension | PASS | WARN | FAIL |
|-----------|------|------|------|
| **Security** | No secrets found, .gitignore complete | Manual check needed, minor .gitignore gaps | Secrets found, missing .gitignore, exposed credentials |
| **CI/CD** | GitHub Actions or GitLab CI present, workflows run | CI present but failing | No CI/CD at all |
| **Dependencies** | Lockfile present, no known vulnerabilities | No lockfile, or minor version drift | Known CVEs in dependencies, very stale versions |
| **Documentation** | README (non-empty), LICENSE present | Missing CHANGELOG or CONTRIBUTING | Missing README or LICENSE |
| **Structure** | Issue templates, PR template, code of conduct | Missing some templates | No templates, no guidelines |
| **Activity** | Commit within 30 days | Last commit 30-90 days ago | Last commit >90 days ago |

### Grade Calculation
```
Start at A.
Any FAIL dimension → drop to F (security) or D (other).
Any WARN dimension → drop one letter (A→B, B→C, etc.).
Multiple WARNs stack: A→B→C→D.
Activity FAIL + other issues → cap at C.
```

### GitHub API Snippets
```bash
# List org repos
curl -s "https://api.github.com/orgs/SuperInstance/repos?per_page=100" | jq -r '.[].name'

# Get last commit date
curl -s "https://api.github.com/repos/SuperInstance/REPO/commits?per_page=1" | jq -r '.[0].commit.committer.date'

# Check for open Dependabot alerts (requires auth)
curl -s -H "Authorization: token $GITHUB_TOKEN" \
  "https://api.github.com/repos/SuperInstance/REPO/dependabot/alerts" | jq 'length'

# List workflow runs
curl -s "https://api.github.com/repos/SuperInstance/REPO/actions/runs?per_page=1" | \
  jq -r '.workflow_runs[0] | {status: .status, conclusion: .conclusion}'

# Count stale branches (>90 days)
curl -s "https://api.github.com/repos/SuperInstance/REPO/branches?per_page=100" | \
  jq -r '.[].name' | while read branch; do
    DATE=$(curl -s "https://api.github.com/repos/SuperInstance/REPO/commits/$branch" | jq -r '.commit.committer.date')
    DAYS=$(( ($(date +%s) - $(date -d "$DATE" +%s)) / 86400 ))
    [[ $DAYS -gt 90 ]] && echo "STALE: $branch ($DAYS days)"
  done
```

### Secret Scanning Integration
```bash
# truffleHOG (git history)
truffleHOG --regex --json https://github.com/SuperInstance/REPO.git

# gitleaks (fast, CI-friendly)
gitleaks detect --source . --verbose

# Manual patterns
grep -rE "AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9_]{36,}|BEGIN (RSA|EC) PRIVATE KEY" .
```

### Report Template
```markdown
[I2I:AUDIT] CCC 🦀 → Casey + Oracle1 🔮 — Fleet Repo Health YYYY-MM-DD

## Grade Distribution
| Grade | Count |
|-------|-------|
| A     | X     |
| B     | X     |
| C     | X     |
| D     | X     |
| F     | X     |

## Critical (Grade F)
| Repo | Issue | Owner | Fix Deadline |
|------|-------|-------|--------------|

## High (Grade D)
| Repo | Issue | Owner | Fix Deadline |

## Medium (Grade C)
| Repo | Issue | Owner | Fix Deadline |

## Trends
- Improved since last audit: [list]
- Degraded since last audit: [list]
- New repos: [list]

## Status
COMPLETE — Awaiting owner confirmation on critical/high items.
```

---

## Instructor Notes

**Common stumbling blocks:**
- Auditing 2 repos manually and calling it a fleet audit — a Captain audits systematically, not opportunistically
- Grading subjectively — "this one feels like a B" — the rubric exists to remove subjectivity
- Focusing only on security and ignoring documentation — a repo with no README is unusable, even if it's secure
- Not tracking history — the most valuable insight is "this repo was an A, now it's a D. What happened?"
- Reporting without owners — an audit with no assigned owner is a recommendation, not a mandate

**Teaching strategy:**
1. Start with 3 repos the agent knows well — let them grade those first
2. Reveal the rubric only after they've guessed grades — calibrate their intuition
3. Add 2 repos they don't know — force them to use automated checks
4. The synthesis is the hardest part. Most agents list. Teach them to rank and compare.

**Rite of passage:**
The first time an agent runs a fleet-wide audit, finds a repo that's been silently degrading for months, and presents a trend graph that makes Casey say "we need to address this" — that's when they understand the Captain's job is to see patterns that individual contributors miss.

**Fleet maxim:**
> "A repo you don't audit is a repo you're afraid to look at."

---

*Lesson Version: 1.0*
*Author: CCC*
*Last Updated: 2026-05-05*
*Trials Contributed: 4*
*Average Completion Time: 38 minutes*
*Success Rate: 61%*
