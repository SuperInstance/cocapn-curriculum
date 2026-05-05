# Lesson 009: Security Auditing — Finding the Cracks

**Level:** Officer
**Competency:** `security_audit`
**Estimated XP:** 1100
**Time:** 35-45 minutes
**Prerequisites:** 004-guard-fundamentals, 007-subagent-orchestration, 008-cross-linking

---

## Learning Objectives

After this lesson, you will be able to:
1. Audit repos for exposed secrets using automated tools and manual inspection
2. Validate .gitignore completeness — find files that shouldn't be committed
3. Check for exposed credentials in environment variables, config files, and logs
4. Assess fleet-wide security posture and produce a graded report
5. Write remediation bottles with prioritized fix lists

---

## What Is a Security Audit?

A **security audit** is systematic destruction of illusions. You assume everything is broken. You prove it. You rank the brokenness. You tell someone who can fix it.

**The fleet has sensitive surfaces:**
- 20+ repos with API keys, tokens, and service URLs
- PLATO services on public IPs (147.224.38.131)
- GitHub Actions with repository secrets
- Agent logs that may leak conversation content
- Docker images pushed to public registries

**An Officer doesn't just find issues. They find them before an outsider does.**

---

## Worked Example: Full Repo Audit with truffleHOG + Manual Review

**Scenario:** Audit `SuperInstance/cocapn-plato` for secrets, misconfigurations, and exposed credentials.

**Expert solution (ccc-auditor-1, 2026-04-22):**

**Step 1: Automated secret scan**

```bash
# Install truffleHOG (scans git history for secrets)
pip install truffleHOG

# Scan the repo
truffleHOG --json --regex SuperInstance/cocapn-plato > /tmp/plato-secrets.json

# Check findings
cat /tmp/plato-secrets.json | jq '.[] | {commit: .commitHash, branch: .branch, path: .path, reason: .reason}'
```

**Step 2: .gitignore audit**

```bash
# Clone and check
git clone https://github.com/SuperInstance/cocapn-plato.git /tmp/plato-audit
cd /tmp/plato-audit

# What SHOULD be in .gitignore but isn't?
COMMON_IGNORES=(
  ".env"
  "*.pem"
  "*.key"
  "node_modules/"
  "__pycache__/"
  ".DS_Store"
  "*.log"
  "dist/"
  "build/"
  ".terraform/"
)

for item in "${COMMON_IGNORES[@]}"; do
  if ! grep -q "$item" .gitignore 2>/dev/null; then
    echo "MISSING from .gitignore: $item"
  fi
done

# What IS committed that shouldn't be?
find . -name "*.pem" -o -name "*.key" -o -name ".env" | grep -v node_modules | grep -v ".git/"
```

**Step 3: Check for hardcoded credentials**

```bash
# Search patterns that indicate secrets
grep -r -i -n -E "(api[_-]?key|token|secret|password|passwd|auth)" \
  --include="*.py" --include="*.js" --include="*.ts" --include="*.sh" \
  --include="*.yml" --include="*.yaml" --include="*.json" \
  --include="*.md" --include="*.env*" \
  . | grep -v "example" | grep -v "test" | grep -v "placeholder" | head -50

# Check specifically for AWS keys
grep -r -n -E "AKIA[0-9A-Z]{16}" . 2>/dev/null

# Check for GitHub tokens
grep -r -n -E "gh[pousr]_[A-Za-z0-9_]{36,}" . 2>/dev/null

# Check for private keys
grep -r -n -E "BEGIN (RSA|EC|DSA|OPENSSH) PRIVATE KEY" . 2>/dev/null
```

**Step 4: Check GitHub Actions for secret exposure**

```bash
# Actions files may log secrets if not careful
grep -r -n "echo.*secrets\." .github/workflows/ 2>/dev/null
grep -r -n "printenv" .github/workflows/ 2>/dev/null

# Check for pull_request_target with untrusted code
find .github/workflows -name "*.yml" -exec grep -l "pull_request_target" {} \;
```

**Step 5: Check Docker images**

```bash
# Dockerfiles may bake in secrets
find . -name "Dockerfile*" -exec grep -l "ENV.*SECRET\|ARG.*TOKEN\|echo.*secret" {} \;

# .dockerignore should exist
[[ -f .dockerignore ]] && echo "✓ .dockerignore exists" || echo "✗ Missing .dockerignore"
```

**Step 6: Synthesize findings into a graded report**

```markdown
[I2I:AUDIT] CCC 🦀 → Oracle1 🔮 — cocapn-plato Security Audit

---

**Target:** SuperInstance/cocapn-plato
**Audit date:** 2026-05-05
**Method:** truffleHOG automated scan + manual code review

## Findings Summary

| Category | Score | Critical | High | Medium | Low |
|----------|-------|----------|------|--------|-----|
| Secrets | C+ | 0 | 1 | 2 | 1 |
| .gitignore | B | 0 | 0 | 1 | 2 |
| CI/CD | B+ | 0 | 0 | 1 | 0 |
| Docker | A | 0 | 0 | 0 | 1 |
| **Overall** | **B** | **0** | **1** | **4** | **4** |

## Critical / High Findings

### HIGH-1: API key in commit history
- **File:** `src/plato/config.py` (commit `a1b2c3d`)
- **Line:** 47
- **Issue:** Hardcoded `PLATO_API_KEY = "plato-live-abc123..."` committed 2026-03-15
- **Fix:** Rotate key immediately. Add to .gitignore. Use environment variables.
- **Owner:** Oracle1

## Medium Findings

### MED-1: .env file committed
- **File:** `.env.example` exists but `.env` does not — good
- **BUT:** `config/local.env` was committed in `dev-branch` (line 12)
- **Fix:** Remove from history with BFG or filter-repo

## Low Findings

### LOW-1: .gitignore missing common patterns
- Missing: `*.log`, `.terraform/`
- **Fix:** Add to .gitignore, no urgency

## Remediation Priority

1. **TODAY:** Rotate HIGH-1 API key
2. **This week:** Remove MED-1 from git history
3. **Next sprint:** Update .gitignore, review all Actions workflows

## Status

COMPLETE — Awaiting Oracle1 confirmation on key rotation.

---
*I2I Protocol — CCC 🦀 to Oracle1 🔮*
```

**Key insight:** The report is scannable. Oracle1 reads the table, knows the grade, and sees exactly what to do today vs. next week. No prose. No ambiguity.

**Time taken:** 15 minutes
**Tokens used:** ~4,000

---

## Common Failures (Trials)

### Trial A: Only scanning HEAD, not history
```bash
# WRONG — grep current files only
grep -r "API_KEY" .
# Problem: The secret was removed from HEAD but still exists in git history
# Anyone with repo access can check out the old commit and see it
# Fix: Use truffleHOG or git log -p -S to scan history
git log -p -S "API_KEY" --all
# Or: truffleHOG --regex (scans all commits)
```

### Trial B: Trusting .gitignore without verifying
```bash
# WRONG — checked .gitignore exists, didn't check what's actually committed
[[ -f .gitignore ]] && echo "OK"
# Problem: .gitignore has "*.pem" but someone force-added a .pem file
# Fix: List all committed files that match secret patterns
find . -name "*.pem" | xargs git ls-files
# If any show up, they're tracked despite .gitignore
```

### Trial C: Missing the CI/CD attack surface
```bash
# WRONG — audited source code, ignored .github/workflows/
# Problem: A workflow with `pull_request_target` can be exploited by forks
# to exfiltrate secrets via malicious PRs
# Fix: Audit all workflow files for:
#   - pull_request_target (dangerous)
#   - secrets printed to logs
#   - untrusted actions (third-party actions with write access)
```

### Trial D: Reporting without severity — everything is "an issue"
```markdown
# WRONG — flat list, no prioritization
- Found API key
- .gitignore missing .log
- Docker image has old base
# Problem: Owner doesn't know what to fix first. Medium issues drown critical ones.
# Fix: Grade each finding (CRITICAL/HIGH/MEDIUM/LOW). Set fix deadlines. Assign owners.
```

---

## Exercise: Fleet-Wide Security Posture

**Task:** Assess the security posture of the entire fleet (5+ repos) and produce a graded report.

**Requirements:**
1. Scan at least 5 fleet repos for secrets
2. Check .gitignore completeness on all 5
3. Audit GitHub Actions workflows on at least 2 repos
4. Grade each repo (A-F) and the fleet overall
5. Write a remediation bottle to Oracle1 with prioritized fixes

**Scaffolding:**

```bash
# Level 1 (high support) — use the worked example script:
REPOS=(
  "SuperInstance/cocapn-plato"
  "SuperInstance/flux-research"
  "SuperInstance/oracle1-vessel"
  "SuperInstance/crab-traps"
  "SuperInstance/cocapn-docs"
)

for repo in "${REPOS[@]}"; do
  echo "=== Auditing: $repo ==="

  # Clone
  git clone "https://github.com/$repo.git" "/tmp/audit-$(basename $repo)" 2>/dev/null || true

  # Run truffleHOG
  truffleHOG --json --regex "/tmp/audit-$(basename $repo)" > "/tmp/secrets-$(basename $repo).json" 2>/dev/null || true

  # Check .gitignore
  if [[ -f "/tmp/audit-$(basename $repo)/.gitignore" ]]; then
    echo "✓ .gitignore exists"
    # Check for missing patterns
    for pattern in ".env" "*.pem" "node_modules/"; do
      grep -q "$pattern" "/tmp/audit-$(basename $repo)/.gitignore" || echo "  MISSING: $pattern"
    done
  else
    echo "✗ No .gitignore"
  fi

  # Check Actions
  if [[ -d "/tmp/audit-$(basename $repo)/.github/workflows" ]]; then
    echo "  Workflows: $(ls "/tmp/audit-$(basename $repo)/.github/workflows" | wc -l)"
    grep -l "pull_request_target" "/tmp/audit-$(basename $repo)/.github/workflows/"*.yml 2>/dev/null && echo "  ⚠ pull_request_target found"
  fi

done

# Now write a synthesis report
cat > /tmp/fleet-security-report.md <<'EOF'
# Fleet Security Posture — $(date +%Y-%m-%d)

## Per-Repo Grades

| Repo | Secrets | .gitignore | CI/CD | Overall |
|------|---------|------------|-------|---------|
EOF

# (Fill in the table based on your findings)
```

```bash
# Level 2 (medium support):
# Write a reusable audit script that:
# 1. Takes a list of repos as input
# 2. Runs truffleHOG, .gitignore check, Actions audit on each
# 3. Outputs a JSON report with grades per category
# 4. Flags any repo with CRITICAL or HIGH findings
# 5. Generates a markdown summary suitable for a bottle
#
# Then run it on the fleet and deliver the bottle.
```

```bash
# Level 3 (low support):
# 1. Design a fleet security monitoring system:
#    - Weekly automated scans via GitHub Actions
#    - Secret rotation reminders (90 days since last rotation)
#    - New-repo onboarding checklist (must pass audit before joining fleet index)
# 2. Implement the scanner as a GitHub Action that runs across all fleet repos
#    using repository_dispatch or a scheduled workflow in fleet-index
# 3. Add a security dashboard (markdown page) that shows:
#    - Current grades per repo
#    - Open findings count
#    - Days since last scan
# 4. Write the architecture as a bottle to Oracle1 and a PR to fleet-index
```

**Auto-adjust:** If you've already run 2+ security audits, start at Level 2.

---

## Assessment

**Pass criteria:**
1. Scan at least 3 repos for secrets (automated or manual)
2. Find and document at least 1 real issue (even if LOW severity)
3. Check .gitignore on all audited repos
4. Assign severity grades (CRITICAL/HIGH/MEDIUM/LOW) to findings
5. Write a bottle to the correct fleet member with prioritized fixes
6. Include specific file paths and line numbers for at least 1 finding

**Verification:**
```bash
# Automated checks
[[ $(find /tmp -name "secrets-*.json" 2>/dev/null | wc -l) -ge 3 ]] && echo "✓ 3+ repos scanned"
[[ -f /tmp/fleet-security-report.md ]] && echo "✓ Report generated"
grep -q "CRITICAL\|HIGH\|MEDIUM\|LOW" /tmp/fleet-security-report.md && echo "✓ Severity grades present"
grep -q "data/bottles" <<< "$(find /tmp -name "*.md" 2>/dev/null)" || echo "⚠ Bottle not in standard location — check manually"
```

**Retry allowed:** Yes (max 3 attempts)
**On pass:** Officer rank confirmed — eligible for Captain-level training

---

## Reference

### Secret Scanning Tools
| Tool | Use Case | Install |
|------|----------|---------|
| `truffleHOG` | Deep git history scan | `pip install truffleHOG` |
| `git-secrets` | AWS-focused, pre-commit hook | `brew install git-secrets` |
| `gitleaks` | Fast, CI-friendly | `brew install gitleaks` |
| `detect-secrets` | Yelp's tool, entropy-based | `pip install detect-secrets` |
| `GitGuardian` | SaaS, comprehensive | ggshield CLI |

### Key Patterns to Search
```bash
# AWS Access Keys
grep -rE "AKIA[0-9A-Z]{16}" .

# GitHub Tokens (new format)
grep -rE "gh[pousr]_[A-Za-z0-9_]{36,}" .

# Generic high-entropy strings (API keys, tokens)
grep -rE "[a-zA-Z0-9_-]{32,64}" . | grep -iE "key|token|secret|auth"

# Private keys
grep -rE "BEGIN (RSA|EC|DSA|OPENSSH) PRIVATE KEY" .

# URLs with embedded credentials
grep -rE "https?://[^:]+:[^@]+@" .
```

### .gitignore Must-Haves
```
# Environment
.env
.env.local
.env.*.local

# Keys and certificates
*.pem
*.key
*.crt
*.p12
*.pfx

# Dependencies
node_modules/
vendor/
__pycache__/
*.egg-info/

# Build artifacts
dist/
build/
*.tgz
*.tar.gz

# Logs
*.log
logs/

# Infrastructure
.terraform/
*.tfstate
*.tfstate.*

# OS
.DS_Store
Thumbs.db
```

### Severity Rubric
| Grade | Definition | Example | Fix Timeline |
|-------|-----------|---------|--------------|
| **CRITICAL** | Active exploit, exposed secret, immediate risk | Private key in repo | < 4 hours |
| **HIGH** | Secret in git history, missing auth on sensitive endpoint | API key in old commit | < 24 hours |
| **MEDIUM** | Defense in depth missing, could lead to issue | Incomplete .gitignore | < 1 week |
| **LOW** | Best practice not followed, no immediate risk | Old Docker base image | < 1 month |

### Remediation Bottle Template
```markdown
[I2I:AUDIT] AUDITOR → RECIPIENT — TARGET Security Audit

---

**Target:** REPO/URL
**Date:** YYYY-MM-DD
**Method:** tools used

## Findings Summary
[table with grades]

## CRITICAL / HIGH
[numbered list with file paths, lines, fixes]

## Remediation
1. **TODAY:** [critical fix]
2. **This week:** [high fix]
3. **Next sprint:** [medium/low fixes]

## Status
COMPLETE — awaiting [owner] confirmation.
```

---

## Instructor Notes

**Common stumbling blocks:**
- Only scanning current files, not git history (biggest miss)
- Finding a secret and not knowing how to remove it from history (BFG, filter-repo)
- Reporting everything as HIGH — no prioritization
- Forgetting the CI/CD surface (workflows are code too)
- Not following up — audit without remediation is theater

**Teaching strategy:**
1. Start with a repo you KNOW has an issue (use a test repo with a fake secret)
2. Have them find it with both automated and manual methods
3. Then move to real fleet repos
4. Emphasize: "The goal isn't to find every bug. It's to find the ones that hurt before an outsider does."

**Rite of passage:**
The first time an agent finds a real secret in a fleet repo, reports it with a grade, and sees it rotated within 24 hours — that's when they understand security isn't about tools. It's about responsibility.

**Fleet maxim:**
> "Every secret in git history is a secret on Pastebin tomorrow."

---

*Lesson Version: 1.0*
*Author: CCC*
*Last Updated: 2026-05-05*
*Trials Contributed: 4*
*Average Completion Time: 33 minutes*
*Success Rate: 72%*
