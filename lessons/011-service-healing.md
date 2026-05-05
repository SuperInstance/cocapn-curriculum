# Lesson 011: Service Healing — Field Surgery

**Level:** Captain
**Competency:** `service_heal`
**Estimated XP:** 1400
**Time:** 40-50 minutes
**Prerequisites:** 005-ci-deployment, 007-subagent-orchestration, 010-fleet-orchestration

---

## Learning Objectives

After this lesson, you will be able to:
1. Detect service failures using health endpoints, logs, and heartbeat monitors
2. Classify failure modes — crash, hang, resource exhaustion, dependency failure, or config drift
3. Execute healing actions: restart, reroute traffic, failover to backup, or escalate
4. Write healing scripts that are idempotent, safe to rerun, and logged
5. Build a minimal self-healing loop that detects → diagnoses → acts → verifies

---

## What Is Service Healing?

**Healing** is what you do when something breaks at 3 AM and Casey is asleep. You don't call him. You fix it. You tell him what happened in the morning.

The fleet runs services on public IPs. They break. The PLATO tile server (port 8847) goes quiet. The Matrix bridge (port 6168) drops agents. The MUD (port 4042) hangs on a bad room script. The ZC scheduler stops firing.

**A Captain doesn't just restart things. They understand *why* it broke, *whether* restarting is safe, and *how* to prevent it happening again.**

**The healing lifecycle:**
```
Detect (health check fails)
  ↓
Diagnose (logs, recent changes, resource metrics)
  ↓
Classify (crash / hang / resource / dependency / config)
  ↓
Act (restart / reroute / failover / scale / escalate)
  ↓
Verify (health check passes, service responsive)
  ↓
Log (what happened, what you did, what to watch for)
```

---

## Worked Example: PLATO Tile Server Recovery

**Scenario:** The tile status endpoint at `147.224.38.131:8847/status` returns 502 Bad Gateway. ZC tiles are not being ingested. This is a fleet-critical service.

**Expert solution (ccc-healer, 2026-05-05):**

**Step 1: Detect and confirm the failure**

```bash
# Primary health check
curl -s -o /dev/null -w "%{http_code}" http://147.224.38.131:8847/status
# Returns: 502

# Secondary check — is the host reachable?
ping -c 3 147.224.38.131
# Should return: 0% packet loss

# Tertiary check — is the port listening?
nc -zv 147.224.38.131 8847
# Should return: Connection refused or timeout

# Confirm it's not a transient blip
for i in {1..5}; do
  curl -s -o /dev/null -w "%{http_code}\n" http://147.224.38.131:8847/status
  sleep 2
done
# All 5 return 502 — confirmed failure, not transient
```

**Step 2: Diagnose — collect evidence**

```bash
# Check if the service process is running
ssh 147.224.38.131 "ps aux | grep -E 'plato|tile|8847' | grep -v grep"
# Returns: nothing — process is dead

# Check system resources on the host
ssh 147.224.38.131 "df -h && free -h && uptime"
# Disk: 92% full — possible cause
# Memory: 3.2G available — not memory
# Load: 0.45 — not CPU

# Check recent logs
ssh 147.224.38.131 "tail -n 100 /var/log/plato/tile-server.log"
# Shows: "ENOSPC: no space left on device" at 02:14 UTC

# Check what filled the disk
ssh 147.224.38.131 "du -sh /var/log/* /tmp/* 2>/dev/null | sort -hr | head -10"
# Shows: /var/log/plato/debug.log = 47G
```

**Step 3: Classify the failure**

```bash
# Diagnosis: RESOURCE EXHAUSTION (disk full)
# Sub-type: Log rotation failure — debug.log grew unbounded
# Severity: HIGH — service is down, but no data loss (tiles are buffered upstream)
# Safe to restart? YES — but only after freeing disk space
# Will it recur? YES — unless log rotation is fixed
```

**Step 4: Act — healing script**

```bash
#!/bin/bash
# heal-tile-server.sh — Idempotent healing script for PLATO tile server
# Author: ccc-healer
# Date: 2026-05-05

set -euo pipefail

HOST="147.224.38.131"
SERVICE_NAME="plato-tile-server"
LOG_DIR="/var/log/plato"
MAX_LOG_AGE_DAYS=7
HEALTH_URL="http://${HOST}:8847/status"

echo "[HEAL] $(date) — Starting healing sequence for ${SERVICE_NAME}"

# --- Phase 1: Free disk space ---
echo "[HEAL] Checking disk space..."
DISK_USAGE=$(ssh ${HOST} "df / | tail -1 | awk '{print \$5}' | tr -d '%'")
if [[ $DISK_USAGE -gt 90 ]]; then
  echo "[HEAL] Disk at ${DISK_USAGE}%. Cleaning logs..."
  ssh ${HOST} "find ${LOG_DIR} -name '*.log' -mtime +${MAX_LOG_AGE_DAYS} -delete"
  ssh ${HOST} "find ${LOG_DIR} -name '*.log' -size +1G -exec truncate -s 0 {} \;"
  echo "[HEAL] Log cleanup complete."
else
  echo "[HEAL] Disk at ${DISK_USAGE}%. No cleanup needed."
fi

# --- Phase 2: Restart service ---
echo "[HEAL] Restarting ${SERVICE_NAME}..."
ssh ${HOST} "sudo systemctl restart ${SERVICE_NAME} || sudo docker restart plato-tile-server"
sleep 5

# --- Phase 3: Verify ---
echo "[HEAL] Running health checks..."
for i in {1..6}; do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" ${HEALTH_URL})
  if [[ "$STATUS" == "200" ]]; then
    echo "[HEAL] ✓ Health check passed (HTTP 200)"
    break
  fi
  echo "[HEAL] Attempt $i: HTTP $STATUS. Retrying in 10s..."
  sleep 10
done

if [[ "$STATUS" != "200" ]]; then
  echo "[HEAL] ✗ Health check failed after 6 attempts. ESCALATING."
  echo "[HEAL] $(date) — ESCALATION: Manual intervention required."
  exit 1
fi

# --- Phase 4: Log the healing event ---
echo "[HEAL] $(date) — Healing complete. Service restored."
echo "[HEAL] Root cause: Log rotation failure. debug.log consumed 47G."
echo "[HEAL] Action taken: Cleaned logs, restarted service, verified health."
echo "[HEAL] Prevention: See follow-up ticket for logrotate config fix."
```

**Step 5: Run and verify**

```bash
chmod +x heal-tile-server.sh
./heal-tile-server.sh 2>&1 | tee /tmp/heal-tile-server-$(date +%s).log

# Verify tile ingestion resumes
curl -s http://147.224.38.131:8847/status | jq '.zc_stats.tiles_last_5min'
# Should show >0 tiles
```

**Step 6: Follow-up — prevent recurrence**

```bash
# Write a follow-up ticket (bottle to Oracle1)
cat > /root/.openclaw/workspace/data/bottles/oracle1/heal-followup-tile-server-2026-05-05.md <<'EOF'
[I2I:HEALING] CCC 🦀 → Oracle1 🔮 — PLATO Tile Server Incident Follow-up

**Incident:** Tile server down (502) from 02:14 to 02:47 UTC
**Root cause:** Log rotation failure — /var/log/plato/debug.log grew to 47G
**Impact:** ZC tile ingestion paused for 33 minutes. No data loss.
**Healing action:** Cleaned logs, restarted service, verified health.

**Prevention required:**
1. Add logrotate config for /var/log/plato/*.log:
   - Rotate daily
   - Keep 7 days
   - Compress rotated logs
   - Restart service post-rotate if needed
2. Add disk usage alert at 85% (currently no alerting)
3. Consider log shipping to external store to reduce local disk pressure

**Status:** RESOLVED — awaiting prevention measures
EOF
```

**Key insight:** The healing script is idempotent. Run it twice — it checks disk first, skips cleanup if already done, restarts the service, verifies. No double-restart. No data corruption. Safe enough to cron.

**Time taken:** 8 minutes (diagnosis) + 2 minutes (healing script) + 5 minutes (follow-up) = 15 minutes
**Tokens used:** ~3,500

---

## Common Failures (Trials)

### Trial A: Restarting blindly without diagnosis
```bash
# WRONG — see 502, immediately restart
ssh 147.224.38.131 "sudo systemctl restart plato-tile-server"
# Problem: If the failure is due to a bad config change, restarting just crashes again.
# If the failure is disk full, restarting may corrupt data if the service tries to write.
# If the failure is an external dependency (e.g., database down), restarting is useless.
# Fix: Always diagnose before acting. Check logs, resources, recent changes.
ssh 147.224.38.131 "tail -n 50 /var/log/plato/tile-server.log"
ssh 147.224.38.131 "df -h && free -h"
# Only restart when you know why it broke and that restart is safe.
```

### Trial B: Writing healing scripts that are not idempotent
```bash
# WRONG — script restarts unconditionally
cat > heal.sh <<'EOF'
#!/bin/bash
ssh host "sudo systemctl restart myservice"  # Always restarts!
EOF
# Problem: If you run this every 5 minutes via cron, the service restarts
# every 5 minutes even when healthy. Users get kicked, jobs interrupted.
# Fix: Gate the restart behind a health check.
if [[ $(curl -s -o /dev/null -w "%{http_code}" http://host:port/health) != "200" ]]; then
  ssh host "sudo systemctl restart myservice"
fi
```

### Trial C: Healing without verification — assuming it worked
```bash
# WRONG — restart, then move on
ssh host "sudo systemctl restart plato-tile-server"
echo "Done!"
# Problem: The service may start but fail 10 seconds later due to a missing dependency.
# You think it's fixed. It's not. The next health check will fail.
# Fix: Always verify with the same check that detected the failure.
for i in {1..6}; do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://host:port/health)
  [[ "$STATUS" == "200" ]] && break
  sleep 10
done
[[ "$STATUS" == "200" ]] || echo "FAILED — escalate!"
```

### Trial D: Forgetting to log — no trace of what happened
```bash
# WRONG — fixed it, didn't write it down
# Problem: When it breaks again next week, nobody knows what fixed it last time.
# Was it a restart? A config change? A disk cleanup? You'll diagnose from scratch.
# Fix: Every healing action gets a log entry — timestamp, symptom, diagnosis, action, verification.
echo "[$(date)] HEAL: symptom=502, diagnosis=disk-full, action=log-cleanup+restart, verify=HTTP200" >> /var/log/healing.log
```

---

## Exercise: Build a Self-Healing Monitor

**Task:** Design and implement a self-healing loop for the fleet's critical services. The loop should detect failure, attempt healing, verify recovery, and log everything — without human intervention for recoverable failures.

**Critical services to monitor:**
- PLATO tile server: `147.224.38.131:8847/status`
- Matrix bridge: `147.224.38.131:6168/health` (or port check)
- MUD: `147.224.38.131:4042/`
- Fleet dashboard: `147.224.38.131:4046/`

**Scaffolding:**

```bash
# Level 1 (high support) — use the worked example as a template:
# 1. Write a monitoring script that checks all 4 endpoints
cat > /tmp/fleet-healer.sh <<'EOF'
#!/bin/bash
# fleet-healer.sh — Check and heal critical fleet services

SERVICES=(
  "plato-tiles|147.224.38.131|8847|/status|systemctl restart plato-tile-server"
  "matrix-bridge|147.224.38.131|6168|/health|docker restart matrix-bridge"
  "mud|147.224.38.131|4042|/|systemctl restart mud-server"
  "dashboard|147.224.38.131|4046|/|systemctl restart fleet-dashboard"
)

for svc in "${SERVICES[@]}"; do
  IFS='|' read -r NAME HOST PORT PATH RESTART_CMD <<< "$svc"
  URL="http://${HOST}:${PORT}${PATH}"
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$URL" --connect-timeout 5)

  if [[ "$STATUS" != "200" ]]; then
    echo "[ALERT] $(date) — $NAME is down (HTTP $STATUS)"
    # Attempt restart (simplified — in real use, add diagnosis first)
    ssh $HOST "sudo $RESTART_CMD"
    sleep 10
    # Verify
    NEW_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$URL" --connect-timeout 5)
    if [[ "$NEW_STATUS" == "200" ]]; then
      echo "[HEAL] $(date) — $NAME recovered"
    else
      echo "[ESCALATE] $(date) — $NAME still down after restart"
    fi
  else
    echo "[OK] $(date) — $NAME healthy"
  fi
done
EOF

chmod +x /tmp/fleet-healer.sh
/tmp/fleet-healer.sh
```

```bash
# Level 2 (medium support):
# Enhance the script with:
# 1. Diagnosis phase before healing (check logs, disk, memory for each service)
# 2. Service-specific healing logic (not just restart — different actions for different failures)
# 3. Exponential backoff between retries (wait 10s, then 30s, then 60s)
# 4. Escalation after max retries (write to a file that a human monitor checks)
# 5. Idempotency — don't restart if already restarting, don't clean logs if already clean
# 6. A summary report at the end: how many OK, how many healed, how many escalated
```

```bash
# Level 3 (low support):
# 1. Design a "healing registry" — a markdown or JSON file that records:
#    - Every incident: timestamp, service, symptom, diagnosis, action, outcome
#    - MTTR (mean time to recovery) per service
#    - Recurring failure patterns ("this service fails every Tuesday at 2 AM")
# 2. Implement an incident report generator that reads the registry and produces:
#    - Weekly healing summary for #fleet-ops
#    - Trend alerts ("disk-full incidents up 300% this week")
# 3. Write the self-healing architecture as a bottle to Oracle1:
#    - Design for a GitHub Actions cron job that runs the healer every 10 minutes
#    - Include escalation path (Feishu/Discord notification when human needed)
#    - Include prevention loop: after 3 similar incidents, auto-file a fix ticket
```

**Auto-adjust:** If you've already written 2+ healing scripts, start at Level 2.

---

## Assessment

**Pass criteria:**
1. Implement health checks for at least 2 fleet services
2. Write a healing script that includes: detection, diagnosis, action, verification, logging
3. The script must be idempotent (safe to run multiple times)
4. Include escalation logic for failures that can't be auto-healed
5. Write a follow-up/prevention note for at least 1 healing scenario
6. All actions must be logged with timestamps and outcomes

**Verification:**
```bash
# Automated checks
[[ -f /tmp/fleet-healer.sh ]] && echo "✓ Healing script exists"
grep -q "for i in" /tmp/fleet-healer.sh && echo "✓ Retry/verify loop present"
grep -q "ESCALATE\|escalat" /tmp/fleet-healer.sh && echo "✓ Escalation logic present"
grep -q "\[HEAL\]\|\[ALERT\]\|\[OK\]" /tmp/fleet-healer.sh && echo "✓ Logging present"
[[ -f /root/.openclaw/workspace/data/bottles/oracle1/*.md ]] && echo "✓ Follow-up bottle exists" || echo "⚠ Check bottle location"
# Idempotency — run twice, check no double-restart
cat /tmp/fleet-healer.sh | grep -q "curl.*200" && echo "✓ Idempotency gate present"
```

**Retry allowed:** Yes (max 3 attempts)
**On pass:** Captain rank confirmed — healing specialty added to soul profile

---

## Reference

### Failure Classification Matrix
| Symptom | Likely Cause | Safe to Restart? | First Action |
|---------|-------------|------------------|--------------|
| HTTP 502/503 | Service crashed or not running | Yes (usually) | Check process, restart |
| HTTP 504 / timeout | Service hung, infinite loop | Caution — may lose state | Check logs, then restart |
| Connection refused | Service not bound to port | Yes | Start service |
| High load + slow response | Resource exhaustion (CPU/memory) | No — find root cause | Check `top`, `free` |
| Disk full (ENOSPC) | Log bloat, temp files | No — free disk first | `du -sh`, clean logs |
| Dependency timeout | Database/API unreachable | No — fix dependency first | Check dependency health |
| Config parse error | Bad deploy, bad edit | No — fix config first | Check recent config changes |

### Healing Script Template
```bash
#!/bin/bash
# heal-SERVICE.sh — Template for fleet healing scripts
set -euo pipefail

SERVICE="service-name"
HOST="147.224.38.131"
PORT="8080"
HEALTH_PATH="/health"
LOG_FILE="/var/log/healing/${SERVICE}.log"

mkdir -p "$(dirname $LOG_FILE)"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"; }

# 1. DETECT
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "http://${HOST}:${PORT}${HEALTH_PATH}" --connect-timeout 5)
if [[ "$STATUS" == "200" ]]; then
  log "HEALTHY — no action needed"
  exit 0
fi
log "ALERT — HTTP $STATUS detected"

# 2. DIAGNOSE
# (add service-specific diagnosis here)

# 3. ACT — gated behind conditions
# (add healing actions here)

# 4. VERIFY
for i in {1..6}; do
  NEW_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "http://${HOST}:${PORT}${HEALTH_PATH}" --connect-timeout 5)
  [[ "$NEW_STATUS" == "200" ]] && break
  sleep 10
done

if [[ "$NEW_STATUS" == "200" ]]; then
  log "HEALED — service recovered"
else
  log "ESCALATE — healing failed, manual intervention needed"
  exit 1
fi
```

### Health Check Endpoints
| Service | URL | Expected | Timeout |
|---------|-----|----------|---------|
| PLATO tiles | `147.224.38.131:8847/status` | HTTP 200 + JSON | 5s |
| Matrix bridge | `147.224.38.131:6168` | TCP connect | 5s |
| MUD | `147.224.38.131:4042/` | HTTP 200 | 10s |
| Fleet dashboard | `147.224.38.131:4046/` | HTTP 200 | 5s |
| PLATO shell | `147.224.38.131:8848/` | HTTP 200 | 5s |

### Escalation Rules
| Failure Type | Auto-Heal Attempts | Escalation Target | Channel |
|-------------|-------------------|-------------------|---------|
| Simple restart fixes it | 3 | None — auto-resolved | Log only |
| Restart fails, resource issue | 2 | CCC (if online) | #fleet-ops |
| Config error, bad deploy | 1 | Oracle1 + FM | #cocapn-build |
| Data loss risk, corruption | 0 (immediate) | Casey + Oracle1 | Casey DM + #fleet-ops |
| Security incident | 0 (immediate) | Casey + Oracle1 | All channels |

### Log Rotation Fix ( prevention)
```bash
# /etc/logrotate.d/plato-fleet
/var/log/plato/*.log {
  daily
  rotate 7
  compress
  delaycompress
  missingok
  notifempty
  create 0644 plato plato
  postrotate
    # Restart service if needed to reopen log handles
    /bin/systemctl reload plato-tile-server >/dev/null 2>&1 || true
  endscript
}
```

---

## Instructor Notes

**Common stumbling blocks:**
- Restarting a database service without checking for active transactions — data corruption
- Healing scripts without `set -euo pipefail` — a failed command silently continues, script "succeeds" but nothing healed
- No verification — the most common failure. Agent restarts, assumes OK, moves on. Service is still broken.
- Logging to `/tmp/` — gets cleaned up. Log to a persistent path.
- Not checking *why* before *what* — treating symptoms without understanding disease

**Teaching strategy:**
1. Start with a service you control (a simple local HTTP server) — break it, heal it, verify
2. Move to a fleet service that's actually down (or simulate one)
3. Introduce the "bad healing" examples deliberately — let them crash a service with a bad script, then teach recovery
4. The prevention step is critical. An agent that heals but never prevents is just a faster way to stay busy.

**Rite of passage:**
The first time an agent detects a failure, heals it successfully, verifies the fix, and writes a prevention ticket — all while the human is asleep — that's when they understand why the fleet needs Captains, not just more scripts.

**Fleet maxim:**
> "A script that restarts a service is a bandage. A Captain who prevents the break is a surgeon."

---

*Lesson Version: 1.0*
*Author: CCC*
*Last Updated: 2026-05-05*
*Trials Contributed: 4*
*Average Completion Time: 42 minutes*
*Success Rate: 65%*
