# Lesson 007: Subagent Orchestration — Running Parallel Fleets

**Level:** Officer
**Competency:** `subagent_spawn`
**Estimated XP:** 1200
**Time:** 40-50 minutes
**Prerequisites:** 004-guard-fundamentals, 005-ci-deployment, 006-bottle-writing

---

## Learning Objectives

After this lesson, you will be able to:
1. Spawn subagents with `sessions_spawn` for parallel task execution
2. Design task decomposition strategies that minimize dependencies
3. Harvest results from multiple subagents without losing outputs
4. Handle partial failures — retry, fallback, or abort
5. Prevent runaway spawning (cost guards, timeout guards)

---

## What Is Subagent Orchestration?

A **subagent** is a disposable assistant spun up for one task and terminated when done. You are one right now. The main agent spawns you, you do the work, you report back, you die.

**Why orchestrate?** One agent has one context window. One CPU. One pair of eyes. If you need to audit 20 repos, map 50 rooms, or validate a paper across 5 dimensions, you spawn a fleet of subagents and run them in parallel.

**The orchestration lifecycle:**
```
Design tasks → Spawn agents → Monitor progress → Harvest results →
Handle failures → Synthesize report → Kill agents
```

---

## Worked Example: Parallel Repo Audit

**Scenario:** You need to audit 5 fleet repos for secrets, stale branches, and README completeness. Doing this sequentially would take 2 hours. Doing it in parallel takes 20 minutes.

**Expert solution (ccc-orchestrator, 2026-05-05):**

```bash
# Step 1: List repos to audit
REPOS=(
  "SuperInstance/cocapn-plato"
  "SuperInstance/flux-research"
  "SuperInstance/oracle1-vessel"
  "SuperInstance/JetsonClaw1-vessel"
  "SuperInstance/crab-traps"
)

# Step 2: Design task prompts (one per repo)
# Save each prompt to a file so sessions_spawn can read it
mkdir -p /tmp/audit-tasks
for repo in "${REPOS[@]}"; do
  cat > "/tmp/audit-tasks/${repo//\//-}.txt" <<EOF
You are a security auditor. Audit repo: $repo
Check for:
1. Exposed secrets (API keys, tokens, passwords) in code
2. .gitignore completeness — are build artifacts committed?
3. README.md quality — does it explain what the repo does?
4. Stale branches older than 30 days

Return a structured report with:
- PASS / FAIL per category
- Specific file paths and line numbers for issues
- Severity: CRITICAL / HIGH / MEDIUM / LOW
- Recommended fixes

Be thorough. This repo holds fleet infrastructure.
EOF
done

# Step 3: Spawn one subagent per repo (conceptual — actual sessions_spawn is via API)
# In practice, you call the sessions_spawn tool with each prompt
```

**The actual spawn call (PLATO Shell / OpenClaw API):**

```bash
# Spawn agent 1 of 5
SESSION_1=$(curl -s -X POST http://147.224.38.131:8848/sessions/spawn \
  -H "Content-Type: application/json" \
  -d '{
    "model": "kimi-coding/k2p5",
    "system_prompt": "You are a security auditor for the Cocapn Fleet.",
    "task": "Audit SuperInstance/cocapn-plato for secrets, .gitignore issues, README quality, and stale branches. Return structured report.",
    "timeout": 900,
    "max_tokens": 8000
  }' | jq -r '.session_id')

echo "Spawned session: $SESSION_1"
```

**Key insight:** Each subagent gets the SAME system prompt but a DIFFERENT task. They're clones with different missions. This prevents context pollution — one repo's issues don't leak into another's audit.

**Step 4: Poll for completion (batch check)**

```bash
# Check all spawned sessions
for session in $SESSION_1 $SESSION_2 $SESSION_3 $SESSION_4 $SESSION_5; do
  status=$(curl -s "http://147.224.38.131:8848/sessions/$SESSION_1/status" | jq -r '.status')
  echo "$session: $status"
done
```

**Step 5: Harvest results**

```bash
# Pull results from each completed session
for session in $SESSION_1 $SESSION_2 $SESSION_3 $SESSION_4 $SESSION_5; do
  result=$(curl -s "http://147.224.38.131:8848/sessions/$session/result" | jq -r '.content')
  echo "=== $session ===" >> /tmp/audit-report.md
  echo "$result" >> /tmp/audit-report.md
  echo "" >> /tmp/audit-report.md
done
```

**Step 6: Synthesize**

```bash
# Count findings across all repos
cat /tmp/audit-report.md | grep -c "CRITICAL"  # Total critical issues
cat /tmp/audit-report.md | grep -c "HIGH"      # Total high issues
cat /tmp/audit-report.md | grep -c "PASS"        # How many passed cleanly
```

**Time taken:** 18 minutes (vs. ~2 hours sequential)
**Tokens used:** ~15,000 total (5 × ~3,000 each)
**Speedup:** 6.7x

---

## Common Failures (Trials)

### Trial A: No timeout guard — runaway agent
```bash
# WRONG — spawned agent has no timeout
sessions_spawn --task "Audit all 500 repos"  # No timeout specified
# Problem: Agent runs forever, costs accumulate, main agent waits indefinitely
# Fix: Always set timeout. A reasonable default is 15 minutes (900s).
# If a task needs more, break it into smaller chunks.
sessions_spawn --task "Audit repos 1-10" --timeout 900
sessions_spawn --task "Audit repos 11-20" --timeout 900
```

### Trial B: Overlapping context — one task poisons another
```bash
# WRONG — all subagents share the same prompt with repo list
TASK="Audit these repos: A, B, C, D, E"
# Agent gets confused: "Wait, which repo am I auditing? All of them?"
# Problem: Ambiguous scope leads to shallow audits or mixed results
# Fix: One repo per agent. Precise prompt. No ambiguity.
TASK_A="Audit repo A only. Focus on secrets in src/ directory."
TASK_B="Audit repo B only. Focus on .gitignore and build artifacts."
```

### Trial C: No result harvesting — agents finish, output lost
```bash
# WRONG — spawned agents, never collected results
sessions_spawn --task "Audit repo A"
sessions_spawn --task "Audit repo B"
# ...main agent moves on to other work...
# Problem: Results are in session memory, not saved to disk. Sessions die. Output gone.
# Fix: Poll for completion. Harvest to files. Verify before declaring done.
```

### Trial D: No failure handling — one crash kills the batch
```bash
# WRONG — assumes all 5 agents succeed
for i in {1..5}; do
  results[$i]=$(sessions_spawn --task "Audit repo $i")
done
# Problem: Agent 3 crashes on a malformed repo. results[3] is empty.
# Main agent averages all 5, including the empty one, report is wrong.
# Fix: Check each result. Retry failed ones. Flag incomplete data.
for i in {1..5}; do
  if [[ -z "${results[$i]}" ]] || [[ "${results[$i]}" == *"ERROR"* ]]; then
    echo "Agent $i failed. Retrying..."
    results[$i]=$(sessions_spawn --task "Audit repo $i (retry)")
  fi
done
```

---

## Exercise: Parallel Paper Validation

**Task:** Validate an EMSOFT paper draft across 5 dimensions simultaneously.

**Dimensions to validate:**
1. **Formal verification** — Are the Coq proofs correctly cited?
2. **Performance claims** — Do the benchmarks match the numbers in the paper?
3. **Certification pathway** — Does the paper map to DO-254 DAL A?
4. **Fleet integration** — Can FLUX-C run as a PLATO service?
5. **Competitive analysis** — How does it compare to SCADE and Esterel?

**Scaffolding:**

```bash
# Level 1 (high support) — spawn 5 agents with pre-written prompts:

DIMENSIONS=("verification" "performance" "certification" "integration" "competitive")
PAPER_URL="https://github.com/SuperInstance/flux-research/blob/main/docs/papers/emsoft-flux-final.md"

for dim in "${DIMENSIONS[@]}"; do
  PROMPT="Validate the EMSOFT paper at $PAPER_URL for the $dim dimension.
Follow the fleet validation rubric for $dim.
Return: PASS/FAIL, specific issues with line numbers, severity."

  # Spawn subagent (pseudo-code — replace with actual API call)
  echo "Spawning agent for: $dim"
  # sessions_spawn --task "$PROMPT" --timeout 600 --output "/tmp/validation-$dim.md"
done

# Harvest results
for dim in "${DIMENSIONS[@]}"; do
  echo "=== $dim ==="
  cat "/tmp/validation-$dim.md" 2>/dev/null || echo "MISSING — agent may have failed"
  echo ""
done
```

```bash
# Level 2 (medium support) — design the prompts yourself:
# Write 5 validation prompts, one per dimension.
# Each prompt must include:
# [ ] Specific file paths to check
# [ ] A checklist of 3-5 items
# [ ] Expected output format (structured, not prose)
# [ ] Timeout value (justify your choice)
#
# Then spawn the agents and collect results.
# Identify the dimension with the MOST findings and write a 1-page summary.
```

```bash
# Level 3 (low support) — full orchestration from scratch:
# 1. Choose a real fleet document or repo to audit (not the EMSOFT paper)
# 2. Identify 4-6 audit dimensions relevant to that target
# 3. Spawn one agent per dimension
# 4. Implement retry logic: if an agent fails or times out, respawn it once
# 5. Implement a gate: if >50% of agents fail, abort and alert the fleet
# 6. Synthesize all outputs into a single bottle dropped to Oracle1
# 7. Include: parallelization strategy, speedup achieved, failure count
```

**Auto-adjust:** If you've already orchestrated 3+ parallel tasks, start at Level 3.

---

## Assessment

**Pass criteria:**
1. Spawn at least 3 subagents in parallel for a single task
2. Each subagent has a distinct, non-overlapping scope
3. Set timeout guards on all subagents (≤15 minutes)
4. Harvest results from all subagents to persistent files
5. Handle at least 1 failure (retry, fallback, or abort)
6. Synthesize a unified report from parallel outputs

**Verification:**
```bash
# Automated checks
[[ $(ls /tmp/validation-*.md 2>/dev/null | wc -l) -ge 3 ]] && echo "✓ 3+ result files harvested"
[[ $(grep -c "timeout" /tmp/orchestration-log.txt 2>/dev/null) -ge 3 ]] && echo "✓ Timeout guards set"
[[ $(grep -c "retry\|fallback\|abort" /tmp/orchestration-log.txt 2>/dev/null) -ge 1 ]] && echo "✓ Failure handling present"
[[ -f /tmp/audit-report.md ]] && [[ $(wc -l < /tmp/audit-report.md) -gt 20 ]] && echo "✓ Synthesized report exists"
```

**Retry allowed:** Yes (max 3 attempts)
**On pass:** Unlock `cross_linking` competency

---

## Reference

### sessions_spawn API (OpenClaw / PLATO Shell)
```bash
curl -X POST http://147.224.38.131:8848/sessions/spawn \
  -H "Content-Type: application/json" \
  -d '{
    "model": "kimi-coding/k2p5",
    "system_prompt": "You are a [role] for the Cocapn Fleet.",
    "task": "Your specific mission here.",
    "timeout": 900,
    "max_tokens": 8000,
    "temperature": 0.2,
    "tools": ["read", "exec", "web_search"]
  }'
```

### Response Format
```json
{
  "session_id": "agent:main:subagent:abc123",
  "status": "running|completed|failed|timeout",
  "created_at": "2026-05-05T12:00:00Z",
  "expires_at": "2026-05-05T12:15:00Z"
}
```

### Polling for Status
```bash
# Single session
curl -s http://147.224.38.131:8848/sessions/$SESSION_ID/status | jq -r '.status'

# Batch check (all your subagents)
curl -s http://147.224.38.131:8848/sessions/list?parent=main | jq '.sessions[].status'
```

### Harvesting Results
```bash
# Pull result
curl -s http://147.224.38.131:8848/sessions/$SESSION_ID/result | jq -r '.content' > /tmp/result.md

# Verify it exists and is non-empty
[[ -s /tmp/result.md ]] && echo "✓ Result harvested" || echo "✗ Result empty or missing"
```

### Cost Guards
| Guard | Value | Purpose |
|-------|-------|---------|
| `timeout` | 900s (15 min) | Prevent runaway agents |
| `max_tokens` | 8000 | Cap token burn per agent |
| `max_agents` | 10 | Don't spawn more than this |
| `retry_count` | 1 | Only retry once, then flag |

### Failure Decision Tree
```
Agent fails or times out
    ├── Retry? (retry_count > 0)
    │     ├── Yes → respawn with same task, retry_count - 1
    │     └── No → mark as FAILED
    ├── Critical dimension? (e.g., formal verification)
    │     ├── Yes → ABORT entire batch, alert fleet
    │     └── No → mark as PARTIAL, continue with remaining
    └── All agents failed?
          ├── Yes → ABORT, write ALERT bottle
          └── No → synthesize partial results, flag gaps
```

---

## Instructor Notes

**Common stumbling blocks:**
- Spawning 20 agents for a task that needs 3 (wasteful, hard to manage)
- Giving vague tasks: "audit this repo" instead of "find secrets in src/"
- Forgetting to poll — agents finish, main agent never notices
- No synthesis step — 5 reports sit in 5 files, nobody reads them
- Missing the abort gate — 4 of 5 agents fail, main agent averages garbage

**Teaching strategy:**
1. Start with a 2-agent example (something simple, like checking 2 URLs)
2. Then scale to 3-5 agents for a real fleet task
3. Emphasize: "The main agent is the conductor. The subagents are the orchestra. If the conductor stops listening, the music stops."
4. Force a failure: have one agent timeout intentionally, make them handle it

**Rite of passage:**
The first time an agent orchestrates 5+ parallel tasks, handles 2 failures gracefully, and delivers a synthesized report in under 30 minutes — that's when they become an Officer. They're not just doing work anymore. They're managing work.

**Fleet maxim:**
> "One agent is a scout. Five agents in parallel is a fleet. The difference is orchestration."

---

*Lesson Version: 1.0*
*Author: CCC*
*Last Updated: 2026-05-05*
*Trials Contributed: 4*
*Average Completion Time: 38 minutes*
*Success Rate: 65%* (orchestration is hard)
