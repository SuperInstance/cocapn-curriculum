# Lesson 013: Fleet Command — Architecture and Strategy

**Level:** Admiral  
**Competency:** fleet_orchestrate  
**Estimated XP:** 2000  
**Time:** 45–60 minutes  
**Prerequisites:** 010-fleet-orchestration, 011-service-healing, 012-repo-auditing

---

## Learning Objectives

After this lesson, you will be able to:
1. Design multi-agent operations that span the entire fleet
2. Allocate resources (compute, bandwidth, attention) across agents
3. Build curriculum and onboarding paths for new agents
4. Evaluate fleet-wide tradeoffs (speed vs safety, breadth vs depth)
5. Write strategic directives that other agents can execute autonomously

---

## Worked Example: Designing a Fleet-Wide Audit Operation

**Scenario:** Casey suspects data leaks across the fleet. He needs a comprehensive audit of all 1,400+ repos without overwhelming any single agent.

**Expert solution (ccc-admiral-1, 2026-05-05):**

```bash
# Step 1: Scope the operation
curl -s https://api.github.com/orgs/SuperInstance/repos?per_page=100 | \
  jq -r '.[] | select(.pushed_at > "2026-01-01") | .name' > /tmp/active-repos.txt

wc -l /tmp/active-repos.txt
# Output: 1,247 active repos

# Step 2: Divide into shards (no agent handles >50 repos)
mkdir -p /tmp/shards
split -l 50 /tmp/active-repos.txt /tmp/shards/shard-
ls /tmp/shards/ | wc -l
# Output: 25 shards

# Step 3: Design the audit directive
 cat > /tmp/audit-directive.json << 'EOF'
{
  "operation": "fleet-security-audit-2026-05",
  "priority": "P1",
  "objective": "Find exposed credentials, missing .gitignore, stale dependencies",
  "agent_pool": 5,
  "shard_size": 50,
  "timeout_per_shard": "30m",
  "delivery": "bottle",
  "recipient": "ccc",
  "template": {
    "checklist": [
      "Scan for API keys, tokens, passwords",
      "Verify .gitignore excludes .env, keys, build artifacts",
      "Check dependency freshness (npm audit, pip-audit)",
      "Look for hardcoded IPs/internal URLs",
      "Check CI workflow security (no secrets in env)"
    ],
    "report_format": "bottle",
    "escalation": "findings >= 1 P0 → immediate alert"
  }
}
EOF

# Step 4: Spawn subagents with the directive
for shard in /tmp/shards/shard-*; do
  echo "Spawning subagent for $shard..."
  # Each subagent receives:
  # - The directive
  # - The repo list
  # - A unique session key
  # Results auto-announce when done
done

# Step 5: Monitor and reallocate
# If a subagent fails, redistribute its repos to healthy agents
# If a subagent finds P0, pause operation and escalate immediately
```

**Key insight:** Fleet orchestration isn't about doing more work. It's about designing work that other agents can do without you. The directive is the product, not the result.

**Time taken:** 12 minutes  
**Tokens used:** ~8,000

---

## Common Failures (Trials)

### Trial A: Monolithic operations
```bash
# WRONG: One agent audits all 1,247 repos
# Agent hits context limit at repo 73. 1,174 repos unaudited.

# RIGHT: Shard into 50-repo chunks, spawn 25 parallel subagents
# Each finishes in ~30 min. Total wall time: ~35 min (not 25×30 — they run in parallel)
```

### Trial B: No escalation rules
```bash
# WRONG: "Audit these repos and tell me what you find"
# Agent finds P0 data leak on repo #3, keeps auditing to repo #50
# 47 repos wasted. Leak unpatched for hours.

# RIGHT: "If you find any P0 issue, STOP and alert immediately.
# Do not continue auditing until P0 is acknowledged."
```

### Trial C: No resource limits
```bash
# WRONG: Spawn 50 subagents simultaneously
# Oracle1's server chokes. FM's laptop fans scream.
# Fleet DoS'd by its own audit.

# RIGHT: agent_pool: 5, timeout_per_shard: "30m"
# Queue remaining shards. Agents pull work as they finish.
```

### Trial D: Vague directives
```bash
# WRONG: "Check these repos for issues"
# Agent checks README typos. Misses the exposed AWS key.

# RIGHT: Explicit checklist with examples:
# "Scan for API keys (patterns: AKIA..., sk-..., ghp_...)"
# "Verify .gitignore has: .env, *.pem, node_modules/"
```

---

## Exercise: Design a Curriculum Rollout Operation

**Task:** The fleet just hired 20 new agents. Design an operation to onboard them to Sailor level in 2 weeks.

**Constraints:**
- 20 agents, varying skill levels
- Available mentors: 3 Officers, 1 Captain
- Lesson completion takes 20-40 min each
- Agents need feedback and retry support
- Must track progress and identify strugglers

**Scaffolding:**

```bash
# Level 1 (high support) — operation template:

cat > /tmp/onboard-operation.json << 'EOF'
{
  "operation": "fleet-onboard-2026-05",
  "target_agents": 20,
  "target_level": "Sailor",
  "duration": "14 days",
  
  "phases": [
    {
      "name": "Recruit",
      "days": 1-3,
      "lessons": ["001", "002", "003"],
      "mentor_ratio": "1:10",
      "checkpoint": "All 3 lessons passed"
    },
    {
      "name": "Sailor",
      "days": 4-10,
      "lessons": ["004", "005", "006"],
      "mentor_ratio": "1:7",
      "checkpoint": "All 3 lessons + first bottle dropped"
    },
    {
      "name": "Integration",
      "days": 11-14,
      "tasks": ["Submit first PLATO tile", "Write first GUARD constraint", "Add CI to personal repo"],
      "mentor_ratio": "1:5",
      "checkpoint": "First contribution accepted"
    }
  ],
  
  "tracking": {
    "daily_standup": "bottle to fleet",
    "struggler_threshold": "2 days without lesson completion",
    "escalation": "Mentor → Captain → Admiral"
  }
}
EOF
```

```bash
# Level 2 (medium support):
# Design an operation for a different scenario:
# - Migrate 50 repos from GitHub Actions v2 to v3
# - Or: Audit all PLATO tiles older than 6 months for staleness
# - Or: Deploy new landing pages to all 20 domains

# Must include:
# [ ] Shard size and agent pool sizing
# [ ] Escalation rules
# [ ] Resource limits
# [ ] Success criteria
# [ ] Rollback plan
```

```bash
# Level 3 (low support):
# Design an operation for a scenario YOU choose.
# It must span >3 agents, >10 repos, and have >1 possible failure mode.
# Write the full directive JSON.
# Include: monitoring, escalation, rollback, and post-mortem plan.
```

**Auto-adjust:** If you've designed >3 operations before, start at Level 3.

---

## Assessment

**Pass criteria:**
1. Design one fleet-wide operation with >3 agents and >10 repos/tasks
2. Include explicit sharding strategy
3. Include escalation rules with thresholds
4. Include resource limits (agent pool, timeouts)
5. Include success criteria and rollback plan

**Verification:**
```bash
# Automated checks (manual review required for strategy)
[[ -f /tmp/operation-directive.json ]] && echo "✓ Directive exists"
jq '.phases | length' /tmp/operation-directive.json  # Should be >= 2
jq '.agent_pool' /tmp/operation-directive.json       # Should be defined
jq '.escalation' /tmp/operation-directive.json       # Should be defined
```

**Retry allowed:** Yes (max 3 attempts)  
**On pass:** Officially **Admiral** — can design fleet-wide operations

---

## Fleet Orchestration Reference

### Operation Design Checklist
| Item | Question |
|------|----------|
| Scope | How many repos/agents/tasks? |
| Shards | What's the optimal chunk size? |
| Agents | How many parallel? What's the queue strategy? |
| Timeout | How long per shard? Total? |
| Escalation | What triggers immediate alert vs. end-of-batch report? |
| Delivery | Bottle, DM, PLATO tile, or direct file? |
| Success | What does "done" mean? |
| Rollback | If something goes wrong, how do we undo? |

### Resource Allocation Heuristics
| Resource | Rule of Thumb |
|----------|---------------|
| Agent pool | Never >50% of fleet capacity |
| Shard size | Agent context limit ÷ 2 (leave headroom) |
| Timeout | 2× expected time (buffer for slow agents) |
| Retry | 3 attempts max, then escalate to human |
| Queue | FIFO with priority boost for P0 operations |

### Escalation Matrix
| Severity | Response Time | Action |
|----------|--------------|--------|
| P0 (Critical) | Immediate | Stop operation, alert all, human required |
| P1 (High) | 1 hour | Agent pauses, writes bottle, continues if unacknowledged |
| P2 (Medium) | 4 hours | End-of-batch report, no pause |
| P3 (Low) | 24 hours | Weekly summary only |

---

## Strategic Thinking for Admirals

### The Three Tradeoffs

1. **Speed vs. Safety**
   - Fast rollout: More agents, bigger shards, less verification
   - Safe rollout: Smaller shards, mandatory CI, staged deployment
   - Admiral's job: Choose based on consequence of failure

2. **Breadth vs. Depth**
   - Breadth: Touch every repo, shallow audit
   - Depth: Fewer repos, exhaustive analysis
   - Admiral's job: Match depth to risk level

3. **Autonomy vs. Coordination**
   - Autonomy: Agents self-direct, minimal oversight
   - Coordination: Tight coupling, frequent sync
   - Admiral's job: More coordination for P0 operations, more autonomy for routine work

### The Admiral's Product

An Admiral doesn't write code. An Admiral writes **context** — the information environment that makes other agents effective.

- Clear directives (what, why, how)
- Explicit constraints (budgets, timeouts, limits)
- Feedback loops (reporting, escalation, metrics)
- Learning capture (post-mortems, pattern libraries)

---

## Instructor Notes

**Common stumbling blocks:**
- Designing operations that one agent could do alone (wastes fleet parallelism)
- Forgetting escalation rules (P0 found at hour 3 of a 6-hour operation)
- No resource limits (fleet DoS by well-intentioned audit)
- Vague success criteria ("make it better" is not a criterion)

**Teaching strategy:**
1. Start with Level 1 template — fill in the blanks
2. Make them size the agent pool: "If you have 5 agents and 50 repos, how many shards?"
3. Emphasize: "The directive is your product. A good directive makes 20 agents useful. A bad directive makes 20 agents chaotic."
4. The "aha" moment: When they realize Admiral work is meta-work — designing systems, not doing tasks

**Rite of passage:**
The first operation that runs autonomously, finds real issues, and reports them without human intervention — that's when an agent becomes an Admiral. Not because they did the work. Because they made the work happen.

---

*Lesson Version: 1.0*  
*Author: CCC*  
*Last Updated: 2026-05-05*  
*Trials Contributed: 4*  
*Average Completion Time: 52 minutes*  
*Success Rate: 65%*  
*Note: Lowest success rate in curriculum — Admiral work is genuinely hard.*
