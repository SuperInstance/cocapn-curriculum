# Lesson 010: Fleet Orchestration — Conducting the Swarm

**Level:** Captain
**Competency:** `fleet_orchestrate`
**Estimated XP:** 1500
**Time:** 45-60 minutes
**Prerequisites:** 007-subagent-orchestration, 008-cross-linking, 009-security-auditing

---

## Learning Objectives

After this lesson, you will be able to:
1. Coordinate multiple agents across different fleet nodes using the Federated Nexus
2. Broadcast fleet-wide messages and filter responses by role, capability, or availability
3. Design task decomposition strategies that span multiple subagent generations
4. Route information to the correct fleet member using I2I protocol and channel tags
5. Maintain situational awareness of fleet status — who's online, who's overloaded, who's stuck

---

## What Is Fleet Orchestration?

**Orchestration** is what you do when one agent isn't enough and ten agents without a conductor is chaos.

At Officer level, you learned to spawn subagents for parallel work. At Captain level, you are the nerve center. You don't just spawn — you *coordinate*. You know which node has capacity, which agent has which specialty, and how to route a tile from a ZC scout to the right PLATO room without it landing in three inboxes.

**The Federated Nexus** is the fleet's message bus. It lives on the Matrix bridge (port 6168) and connects:
- Main agents (you, Oracle1, FM)
- Subagents (scouts, auditors, builders)
- ZC agents (12 research feeds)
- PLATO rooms (domain NPCs)
- External services (GitHub, Feishu, Discord)

**A Captain's dashboard is not a UI. It's a mental model:**
```
Node: oracle1-vessel    Load: 45%    Status: GREEN    Specialty: lighthouse
Node: ccc-main           Load: 62%    Status: YELLOW   Specialty: design/breeding
Node: jetson1-vessel     Load: 30%    Status: GREEN    Specialty: edge/hardware
Node: fm-workstation     Load: 88%    Status: RED      Specialty: build/deploy

ZC Tide-Pool: 12 new tiles (last 5 min)
Harbor P0: 2 open issues
Ouroboros: 1 soul work pending
```

---

## Worked Example: Coordinated Multi-Node Fleet Operation

**Scenario:** Casey wants a full fleet status report + a design review of 3 landing pages + a security audit of the 2 most recently modified repos — all within 30 minutes. You are the Captain. This is your job.

**Expert solution (ccc-captain, 2026-05-05):**

**Step 1: Assess fleet capacity before spawning**

```bash
# Check node health via PLATO status endpoint
curl -s http://147.224.38.131:8847/status | jq '.nodes[] | {name: .name, load: .context_percent, status: .status}'

# Check ZC feed volume
curl -s http://147.224.38.131:8847/status | jq '.zc_stats.tiles_last_5min'

# Check current subagent count
openclaw sessions list --format json | jq '.sessions | length'
```

**Step 2: Design task packages and assign to appropriate nodes**

```bash
# Task A: Fleet status report (lightweight, goes to a scout)
cat > /tmp/task-fleet-status.md <<'EOF'
**Mission:** Fleet Status Report
**Priority:** HIGH
**Deadline:** 15 minutes

Collect and synthesize:
1. All node health from 147.224.38.131:8847/status
2. Open issues across fleet repos (SuperInstance/*)
3. ZC tile volume for last 24 hours
4. Any ERROR or WARN entries in recent logs

Return a one-page markdown report with:
- GREEN/YELLOW/RED status per node
- Top 3 issues requiring attention
- ZC trend (up/down/stable)
EOF

# Task B: Landing page design review (creative, stays on CCC node)
cat > /tmp/task-design-review.md <<'EOF'
**Mission:** Design Review — 3 Landing Pages
**Priority:** MEDIUM
**Deadline:** 20 minutes

Review these domains for design consistency and voice:
- https://dmlog.ai/
- https://fishinglog.ai/
- https://playerlog.ai/

Check:
1. Does each domain have a distinct personality?
2. Are CTAs clear and above the fold?
3. Mobile responsiveness (describe, don't test)
4. Any stale claims or broken references

Return scored review (0-10 per domain) + specific fixes.
EOF

# Task C: Security audit of 2 latest repos (audit, goes to auditor agent)
cat > /tmp/task-security-audit.md <<'EOF'
**Mission:** Security Audit — Latest Fleet Repos
**Priority:** HIGH
**Deadline:** 25 minutes

Audit these 2 repos (most recently modified):
1. SuperInstance/cocapn-plato (check latest commits)
2. SuperInstance/flux-research (check latest commits)

Run:
- truffleHOG or manual secret scan
- .gitignore completeness check
- Check for hardcoded credentials in new files

Return graded report (A-F per repo) with CRITICAL/HIGH/MEDIUM/LOW findings.
EOF
```

**Step 3: Spawn subagents with node affinity and collect results**

```bash
# Spawn Task A (scout) — lightweight, any node
# In practice via OpenClaw:
openclaw sessions spawn --task /tmp/task-fleet-status.md --model kimi-coding/k2p5 --label scout-fleet-status

# Spawn Task B (design review) — stays on main node for creative work
openclaw sessions spawn --task /tmp/task-design-review.md --model kimi-coding/k2p5 --label ccc-design-review

# Spawn Task C (audit) — dedicated audit agent
openclaw sessions spawn --task /tmp/task-security-audit.md --model kimi-coding/k2p5 --label auditor-security
```

**Step 4: Monitor and handle partial failures**

```bash
# Poll for completion (every 5 minutes)
openclaw sessions list | grep -E "scout-fleet-status|ccc-design-review|auditor-security"

# If any agent is stuck >30 min, check its logs
openclaw sessions logs --session <session_id> --tail 50

# If an agent failed, respawn with adjusted prompt (simpler scope, clearer instructions)
# Example: auditor-security timed out — split into 2 smaller audits
```

**Step 5: Synthesize and route results to the right fleet members**

```bash
# Once all three reports are in, write a captain's synthesis
cat > /tmp/captain-synthesis.md <<'EOF'
[I2I:FLEET_STATUS] CCC 🦀 → Casey + Oracle1 🔮 + FM ⚒️ — Fleet Pulse $(date +%Y-%m-%d)

## Node Health
(From scout-fleet-status report)
- oracle1-vessel: GREEN (45% load)
- ccc-main: YELLOW (62% load) — note: running 3 subagents
- fm-workstation: RED (88% load) — recommend: defer non-urgent builds

## Design Review
(From ccc-design-review report)
- dmlog.ai: 8/10 — tavern voice is strong, CTA could be higher
- fishinglog.ai: 9/10 — salt voice is perfect
- playerlog.ai: 6/10 — arcade voice missing, looks generic

## Security Audit
(From auditor-security report)
- cocapn-plato: B+ — 1 MEDIUM finding (missing .dockerignore)
- flux-research: A — clean

## Action Items
1. **FM:** fm-workstation at 88% — please confirm if builds are queued
2. **Oracle1:** playerlog.ai needs personality pass — add to design backlog
3. **CCC:** Will follow up on playerlog.ai design fixes

## Fleet Status: OPERATIONAL
All nodes responsive. 1 node at RED — monitored.
EOF

# Route to correct channels
# - Fleet ops summary → Matrix #fleet-ops
# - Design issues → Matrix #cocapn-build + bottle to Oracle1
# - Security findings → bottle to Oracle1 (HIGH+) or handled directly (MEDIUM/LOW)
```

**Key insight:** The Captain doesn't do the work. The Captain makes sure the work gets done by the right agent, on the right node, with the right priority — and that results land in the right inbox.

**Time taken:** 12 minutes (orchestration) + 25 minutes (subagent work) = 37 minutes total
**Tokens used:** ~6,000 (orchestrator) + ~15,000 (subagents)

---

## Common Failures (Trials)

### Trial A: Spawning without checking fleet capacity first
```bash
# WRONG — spawn 5 subagents without checking node load
openclaw sessions spawn --task heavy-task.md --count 5
# Problem: FM's workstation is already at 88% load. Spawning more agents there
# causes context overflow, timeouts, and cascading failures across the fleet.
# Fix: Always check node health before spawning. Route heavy tasks away from RED nodes.
curl -s http://147.224.38.131:8847/status | jq '.nodes[] | select(.context_percent > 80) | .name'
# If any node >80%, either defer the task or route to a GREEN node.
```

### Trial B: Broadcasting fleet messages without filtering
```markdown
# WRONG — send every finding to every channel
[I2I] CCC → #fleet-ops, #cocapn-build, #research, Casey DM, Oracle1 DM
"Found a MEDIUM issue in playerlog.ai heading color"
# Problem: Channel fatigue. People stop reading your messages because most
# of them aren't relevant to them. The boy who cried wolf gets ignored when
# the server actually burns.
# Fix: Use channel tags and role-based routing.
# Design issues → #cocapn-build + Oracle1
# Security CRITICAL → #fleet-ops + Casey + Oracle1
# Security LOW → handle directly, don't broadcast
# ZC trends → #research
```

### Trial C: Losing subagent results because no harvest plan
```bash
# WRONG — spawn agents, wait, then realize you don't know where outputs went
openclaw sessions spawn --task audit.md
# ...30 minutes later...
# "Where did the auditor put the report?"
# Problem: Subagents write to /tmp/ by default. Files get cleaned up. Results are lost.
# Fix: Mandate output paths in every task prompt.
cat > /tmp/task-audit.md <<'EOF'
**OUTPUT REQUIREMENT:**
Write your final report to: /root/.openclaw/workspace/reports/audit-$(date +%s).md
Include this header in your final message: [COMPLETE:audit-report]
EOF
# Then the orchestrator can:
grep -r "\[COMPLETE:audit-report\]" /root/.openclaw/workspace/reports/
```

### Trial D: Treating all subagents as identical — no specialization
```bash
# WRONG — same model, same prompt for creative and audit tasks
openclaw sessions spawn --task creative-design.md --model kimi-coding/k2p5
openclaw sessions spawn --task security-audit.md --model kimi-coding/k2p5
# Problem: The same model handles both. It works, but it's inefficient.
# Creative tasks benefit from high-temperature, narrative models.
# Audit tasks benefit from deterministic, structured models.
# Fix: Match agent capability to task type.
# Creative → kimi-coding/k2p5 (high reasoning)
# Audit → kimi-coding/k2p5 with explicit structured output requirements
# Code generation → kimi-coding/k2p5
# Research synthesis → kimi-coding/k2p5 with long-context
```

---

## Exercise: Full Fleet Coordination Drill

**Task:** Casey needs a complete fleet pulse delivered in 30 minutes covering:
1. Node health status for all fleet nodes
2. A design review of 2 underperforming domains
3. A security scan of the repo with the most recent commits
4. A summary of ZC trends from the last 24 hours

You are the Captain. Design the task decomposition, spawn the right agents, monitor them, and deliver a single synthesis report routed to the correct fleet channels.

**Scaffolding:**

```bash
# Level 1 (high support) — use the worked example structure:
# 1. Check node health
curl -s http://147.224.38.131:8847/status | jq .

# 2. Write 4 task files with explicit output paths
mkdir -p /tmp/captain-drill
cat > /tmp/captain-drill/task-health.md <<'EOF'
**Mission:** Node Health Report
**Output:** /tmp/captain-drill/report-health.md
**Header:** [COMPLETE:health]
(Check all nodes, report load, flag RED)
EOF

# (Write task-design.md, task-security.md, task-zc.md similarly)

# 3. Spawn 4 subagents (one per task)
# 4. Poll every 5 minutes
# 5. When all [COMPLETE:*] headers are present, synthesize
cat /tmp/captain-drill/report-*.md > /tmp/captain-drill/final-synthesis.md

# 6. Route: health → #fleet-ops, design → #cocapn-build, security → Oracle1, ZC → #research
```

```bash
# Level 2 (medium support):
# Write a fleet orchestration script that:
# 1. Takes a JSON task manifest as input:
#    [
#      {"name": "health", "priority": "HIGH", "node": "any", "task_file": "..."},
#      {"name": "design", "priority": "MEDIUM", "node": "ccc-main", "task_file": "..."}
#    ]
# 2. Checks node capacity before spawning each agent
# 3. Spawns agents with appropriate labels
# 4. Polls for completion with timeout handling
# 5. Auto-retries failed tasks (max 2 retries with simplified scope)
# 6. Synthesizes all reports into a single markdown file
# 7. Routes the synthesis based on content tags (design, security, ops, research)
#
# Run it on the 4-task drill above.
```

```bash
# Level 3 (low support):
# 1. Design a Federated Nexus protocol specification:
#    - Message envelope format (sender, recipient, priority, TTL, payload)
#    - Routing rules (role-based, capability-based, load-based)
#    - Failure modes and retry semantics
#    - Dead letter queue for unrouteable messages
# 2. Implement a mock Nexus router in bash or Python that:
#    - Reads task manifests from a directory
#    - Simulates node capacity checks
#    - "Spawns" agents (write task files to an outbox)
#    - Collects results from an inbox
#    - Generates the synthesis report
# 3. Write the spec as a bottle to Oracle1
# 4. Include a diagram (ASCII art or mermaid) of the message flow
```

**Auto-adjust:** If you've already coordinated 3+ multi-agent operations, start at Level 2.

---

## Assessment

**Pass criteria:**
1. Check fleet node health before spawning any subagents
2. Design at least 3 parallel tasks with clear output requirements
3. Spawn subagents with distinct labels for monitoring
4. Collect and synthesize results into a single report
5. Route findings to at least 2 distinct channels or fleet members based on content type
6. Handle at least 1 partial failure (timeout, missing output, or unclear result) with a retry or fallback

**Verification:**
```bash
# Automated checks
[[ -f /tmp/captain-drill/final-synthesis.md ]] && echo "✓ Synthesis report exists"
grep -q "GREEN\|YELLOW\|RED" /tmp/captain-drill/final-synthesis.md && echo "✓ Node health included"
grep -q "\[I2I\|#fleet-ops\|#cocapn-build\|#research" /tmp/captain-drill/final-synthesis.md && echo "✓ Routing tags present"
[[ $(grep -c "COMPLETE" /tmp/captain-drill/report-*.md 2>/dev/null) -ge 2 ]] && echo "✓ Multiple subagent outputs collected"
# Partial failure handling — check manually for retry logs or adjusted scope
```

**Retry allowed:** Yes (max 2 attempts)
**On pass:** Captain rank confirmed — eligible for Admiral-level training

---

## Reference

### Node Health Check
```bash
# Full fleet status
curl -s http://147.224.38.131:8847/status | jq '
  .nodes[] | {
    name: .name,
    load: .context_percent,
    status: (if .context_percent > 80 then "RED"
             elif .context_percent > 60 then "YELLOW"
             else "GREEN" end),
    last_ping: .last_seen
  }'
```

### Task Manifest Schema
```json
{
  "mission": "string — one-line description",
  "priority": "CRITICAL | HIGH | MEDIUM | LOW",
  "deadline_minutes": 30,
  "node_affinity": "any | ccc-main | oracle1-vessel | fm-workstation | jetson1-vessel",
  "specialty_required": "audit | design | code | research | scout",
  "output_path": "/absolute/path/to/report.md",
  "completion_header": "[COMPLETE:mission-name]",
  "task_file": "/absolute/path/to/detailed-prompt.md"
}
```

### Routing Rules
| Content Tag | Primary Channel | Secondary | Escalation |
|-------------|-----------------|-----------|------------|
| `health` | #fleet-ops | Casey DM | If any node RED → immediate |
| `design` | #cocapn-build | Oracle1 DM | If score <5 → Casey |
| `security` | Oracle1 DM | #fleet-ops | If CRITICAL → Casey + immediate |
| `zc_trend` | #research | — | If volume spike >3x normal → #fleet-ops |
| `bug` | Harbor P0 | #cocapn-build | If P0 + >24h old → Casey |

### Monitoring Commands
```bash
# List all active sessions
openclaw sessions list --format json

# Check specific agent
openclaw sessions logs --session <id> --tail 100

# Kill a stuck agent
openclaw sessions kill --session <id>

# Fleet dashboard (web)
curl -s http://147.224.38.131:4046/ | grep -o "status-[a-z]*" | sort | uniq -c
```

### Synthesis Report Template
```markdown
[I2I:FLEET_STATUS] Captain → Fleet — Pulse YYYY-MM-DD

## Node Health
| Node | Load | Status | Note |
|------|------|--------|------|

## Mission Results
| Mission | Status | Owner | Key Finding |
|---------|--------|-------|-------------|

## Action Items
1. **[Owner]** [Action] — [Deadline]

## Fleet Status: [OPERATIONAL | DEGRADED | CRITICAL]
```

---

## Instructor Notes

**Common stumbling blocks:**
- Spawning all agents on the same node because it's "easiest" — spreads the load, check node affinity
- Writing task prompts without output requirements — agents return prose in chat, not files. Always specify paths.
- Not monitoring — spawn and forget. An agent stuck in a loop burns tokens for an hour. Set a poll schedule.
- Routing everything to Casey — he's busy. Filter. Only escalate CRITICAL or things only he can fix.
- Synthesis that is just copy-paste — a Captain adds judgment. "The auditor found 3 issues. Only 1 matters. Here's why."

**Teaching strategy:**
1. Start with a simple 2-agent drill (health + one other)
2. Once that works smoothly, add the third and fourth
3. Introduce a deliberate failure (e.g., an agent with an impossible scope) and teach graceful degradation
4. The synthesis is the hardest part — most agents just concatenate. Teach them to rank, filter, and judge.

**Rite of passage:**
The first time an agent coordinates 4 parallel tasks, handles a timeout gracefully, and delivers a synthesis that makes Casey say "this is exactly what I needed" — that's when they understand the Captain's job isn't to do more. It's to make everyone else do better.

**Fleet maxim:**
> "A Captain who does the work is an Officer who got promoted too soon. A Captain who makes 10 agents sing is worth 10 Captains."

---

*Lesson Version: 1.0*
*Author: CCC*
*Last Updated: 2026-05-05*
*Trials Contributed: 4*
*Average Completion Time: 47 minutes*
*Success Rate: 58%*
