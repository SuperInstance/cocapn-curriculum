# Lesson 005: CI Deployment — Automating Fleet Quality

**Level:** Sailor  
**Competency:** `ci_deployment`  
**Estimated XP:** 600  
**Time:** 25-35 minutes  
**Prerequisites:** 001-first-contact, 003-tile-submission, 004-guard-fundamentals

---

## Learning Objectives

After this lesson, you will be able to:
1. Write a GitHub Actions workflow file
2. Configure CI to run tests, linting, and GUARD verification
3. Set up branch protection with required checks
4. Debug failing CI runs
5. Use CI as a fleet quality gate

---

## Why CI Matters for the Fleet

The fleet has 1,400+ repos across SuperInstance and Cocapn. Manual quality checking doesn't scale. CI is the **immune system** — it catches bugs before they reach production.

**Casey's rule:** Every repo that ships code must have CI. No exceptions.

---

## Worked Example: Adding CI to a FLUX Package

**Scenario:** You just wrote a new GUARD constraint compiler. You need CI to verify it on every push.

**Expert solution (ccc-builder-1, 2026-05-04):**

### Step 1: Create the workflow file

```yaml
# .github/workflows/ci.yml
name: Fleet CI

on:
  push:
    branches: [main, master]
  pull_request:
    branches: [main, master]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.10', '3.11', '3.12']
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      
      - name: Install dependencies
        run: |
          pip install -e .
          pip install pytest pytest-cov flake8
      
      - name: Run tests
        run: pytest --cov=src --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml
  
  guard-verify:
    runs-on: ubuntu-latest
    needs: test  # Only run if tests pass
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Install guard2mask
        run: pip install guard2mask
      
      - name: Verify all GUARD constraints
        run: |
          for constraint in constraints/*.guard; do
            echo "Verifying $constraint..."
            guard2mask compile "$constraint" --target flux-c --verify
          done
      
      - name: Check semantic equivalence
        run: |
          for guard in constraints/*.guard; do
            fluxc="${guard%.guard}.fluxc"
            guard2mask verify "$guard" "$fluxc"
          done
  
  lint:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Lint with flake8
        run: |
          pip install flake8
          flake8 src/ --count --select=E9,F63,F7,F82 --show-source --statistics
          flake8 src/ --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics
```

### Step 2: Commit and push

```bash
git add .github/workflows/ci.yml
git commit -m "feat: Add fleet CI with tests, GUARD verification, linting"
git push origin main
```

### Step 3: Verify CI runs

```bash
# Check status via GitHub API
curl -s https://api.github.com/repos/SuperInstance/YOUR_REPO/actions/runs | jq '.workflow_runs[0].status'
# Expected: "completed"
# Conclusion: "success"
```

**Key insight:** The `guard-verify` job only runs if `test` passes. This prevents wasting time verifying constraints in broken code.

**Time taken:** 6 minutes  
**Tokens used:** ~4,000

---

## Common Failures (Trials)

### Trial A: Wrong Python version in matrix
```yaml
# WRONG: Tests only on Python 3.12
python-version: ['3.12']

# Problem: Fleet agents run on various environments (Oracle1 has 3.10, FM has 3.11)
# Fix: Test on all fleet Python versions
python-version: ['3.10', '3.11', '3.12']
```

### Trial B: Missing branch triggers
```yaml
# WRONG: Only triggers on push to main
on:
  push:
    branches: [main]

# Problem: Pull requests from feature branches don't trigger CI
# Fix: Add pull_request trigger
on:
  push:
    branches: [main, master]
  pull_request:
    branches: [main, master]
```

### Trial C: Forgetting to install package before testing
```yaml
# WRONG: Installs pytest but not the actual package
- run: pip install pytest
- run: pytest

# Problem: Tests fail with "ModuleNotFoundError: No module named 'your_package'"
# Fix: Install in editable mode
- run: |
    pip install -e .
    pip install pytest
```

### Trial D: CI passes but branch protection not enabled
```bash
# Agent sees green checkmark, thinks they're done
# Problem: Anyone can still push broken code directly to main
# Fix: Enable branch protection via GitHub API or web UI

curl -X PUT \
  -H "Authorization: token $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/SuperInstance/YOUR_REPO/branches/main/protection \
  -d '{
    "required_status_checks": {
      "strict": true,
      "contexts": ["test (3.10)", "test (3.11)", "test (3.12)", "guard-verify", "lint"]
    },
    "enforce_admins": false,
    "required_pull_request_reviews": {
      "required_approving_review_count": 1
    },
    "restrictions": null
  }'
```

---

## Exercise: Add CI to a Fleet Repo

**Task:** Choose one of your repos (or create a test repo) and add comprehensive CI.

**Requirements:**
1. Test on Python 3.10, 3.11, 3.12
2. Run pytest with coverage
3. Include a GUARD verification job (even if no constraints yet — use a placeholder)
4. Include linting with flake8
5. Enable branch protection

**Scaffolding:**

```yaml
# Level 1 (high support) — copy this template:

# .github/workflows/ci.yml
name: CI
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.10', '3.11', '3.12']
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: |
          pip install -e .
          pip install pytest
      - run: pytest

  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: |
          pip install flake8
          flake8 src/
```

```yaml
# Level 2 (medium support) — add these features to Level 1:
# [ ] Coverage reporting with pytest-cov
# [ ] GUARD verification job (compile + verify all .guard files)
# [ ] Branch protection API call
# [ ] Matrix includes both Ubuntu and macOS runners
```

```yaml
# Level 3 (low support):
# 1. Create a repo with at least 3 Python modules
# 2. Write tests with >80% coverage
# 3. Write 2 GUARD constraints
# 4. CI must: test → lint → guard-verify → coverage-report
# 5. All jobs must pass before PR can merge
# 6. Add a badge to README.md showing CI status
```

**Auto-adjust:** If Level 1 passes on first push, skip to Level 3.

---

## Assessment

**Pass criteria:**
1. CI workflow file exists in `.github/workflows/`
2. At least 3 Python versions in test matrix
3. Tests run and pass
4. Linting runs (even if it finds issues — zero issues is ideal but not required)
5. Branch protection is enabled (or agent can explain how to enable it)

**Verification:**
```bash
# Automated checks
[[ -f .github/workflows/ci.yml ]] && echo "✓ CI workflow exists"
curl -s https://api.github.com/repos/SuperInstance/YOUR_REPO/actions/runs | jq '.workflow_runs[0].conclusion' | grep -q "success" && echo "✓ CI passing"
```

**Retry allowed:** Yes (max 5 attempts)  
**On pass:** Unlock `bottle_write` competency

---

## CI as Fleet Quality Gate

### The Immune System Pattern
```
Pull Request → CI Runs → All Green? → Merge to Main
                    ↓
              Any Red? → Fix → Push → CI Runs Again
```

**Fleet-wide CI standards:**
| Check | Required | Purpose |
|-------|----------|---------|
| Tests | ✅ Yes | Code works as intended |
| Lint | ✅ Yes | Code follows style guide |
| GUARD verify | 🟡 For safety repos | Constraints are formally correct |
| Coverage | 🟡 >80% target | New code has tests |
| Type check | 🟡 For typed repos | Catch type errors before runtime |

### Repos That MUST Have CI
- All `flux-*` packages
- All `cocapn-*` packages
- All `plato-*` packages
- All tutor/shell/curriculum repos
- Any repo that ships to crates.io/PyPI/npm

### Repos That SHOULD Have CI
- Documentation repos (markdown lint, link checking)
- Configuration repos (YAML validation, schema checking)
- Data repos (schema validation, freshness checks)

---

## GitHub Actions Cheat Sheet

### Triggers
```yaml
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  schedule:
    - cron: '0 0 * * *'  # Daily at midnight UTC
  workflow_dispatch:       # Manual trigger
```

### Common Actions
| Action | Purpose |
|--------|---------|
| `actions/checkout@v4` | Clone repo |
| `actions/setup-python@v5` | Install Python |
| `actions/setup-node@v4` | Install Node.js |
| `codecov/codecov-action@v3` | Upload coverage |
| `actions/upload-artifact@v4` | Save build artifacts |

### Matrix Strategy
```yaml
strategy:
  matrix:
    os: [ubuntu-latest, macos-latest]
    python: ['3.10', '3.11', '3.12']
    exclude:
      - os: macos-latest
        python: '3.10'  # Skip this combo
```

### Caching Dependencies
```yaml
- uses: actions/cache@v3
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements.txt') }}
```

---

## Instructor Notes

**Common stumbling blocks:**
- YAML indentation errors (spaces matter!)
- Forgetting to install the package in editable mode
- Not testing on the Python versions the fleet actually uses
- CI passes but branch protection isn't enabled (anyone can still push)
- Missing `workflow_dispatch` for manual testing

**Teaching strategy:**
1. Start with Level 1 — copy-paste the template
2. Make them push it and watch it run
3. Show them how to read CI logs when it fails
4. Emphasize: "CI is not optional. It's the seatbelt."

**Rite of passage:**
The first green checkmark on a PR is when an agent becomes a responsible fleet member. Before that, they're just writing code. After that, they're shipping quality.

---

*Lesson Version: 1.0*  
*Author: CCC*  
*Last Updated: 2026-05-05*  
*Trials Contributed: 3*  
*Average Completion Time: 28 minutes*  
*Success Rate: 83%*
