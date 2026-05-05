# Lesson 004: GUARD Fundamentals — Constraints That Compile

**Level:** Sailor  
**Competency:** `guard_compilation`  
**Estimated XP:** 800  
**Time:** 30-45 minutes  
**Prerequisites:** 001-first-contact, 002-room-mapping, 003-tile-submission

---

## Learning Objectives

After this lesson, you will be able to:
1. Write a GUARD constraint in the domain-specific language
2. Compile GUARD to FLUX-C bytecode using `guard2mask`
3. Verify the compiled output against the original constraint
4. Execute the bytecode in the FLUX-C VM
5. Debug constraint violations

---

## What Is GUARD?

**GUARD** (Generalized Unified Assertion and Rule Descriptor) is a constraint language for safety-critical systems. It describes what *must* be true, not how to achieve it.

**Key idea:** Write constraints in human-readable form. Compile them to provable bytecode. Execute them in a formally verified VM.

```
GUARD constraint → guard2mask → FLUX-C bytecode → flux-vm → ✓ or ✗
```

---

## Worked Example: Altitude Constraint for eVTOL

**Scenario:** You're writing a safety constraint for an electric vertical takeoff and landing vehicle. The constraint: "Altitude must be between 0 and 400 feet during takeoff."

**Step 1: Write the GUARD constraint**

```guard
constraint_evtol_altitude {
    domain: "aviation",
    purpose: "takeoff_safety",
    
    variables {
        altitude: float,
        phase: enum { TAKEOFF, CRUISE, LANDING }
    },
    
    rule altitude_check {
        when: phase == TAKEOFF
        assert: altitude >= 0.0 AND altitude <= 400.0
        on_violation: EMERGENCY_LANDING
        severity: CRITICAL
    }
}
```

**Key insight:** The constraint name `constraint_evtol_altitude` follows the `domain_purpose` pattern. No bare English words. This prevents the grammar scoping bug that Forgemaster fixed in v0.1.0.

**Step 2: Compile to FLUX-C**

```bash
guard2mask compile constraint_evtol_altitude.guard --target flux-c --output altitude.fluxc
```

**Expected output:**
```
[guard2mask] Parsing constraint_evtol_altitude.guard...
[guard2mask] Type checking... ✓
[guard2mask] Compiling to FLUX-C...
[guard2mask] Generated: altitude.fluxc (12 bytes)
[guard2mask] Verification: semantic equivalence check... ✓
```

**Step 3: Inspect the bytecode**

```bash
flux-asm disassemble altitude.fluxc
```

**Expected output:**
```
; FLUX-C bytecode: altitude_check
; Stack machine, 43-opcode ISA

LOAD_VAR    altitude       ; Push altitude onto stack
LOAD_CONST  0.0            ; Push lower bound
FGE                         ; Float greater-or-equal (altitude >= 0.0)
LOAD_VAR    altitude       ; Push altitude again
LOAD_CONST  400.0          ; Push upper bound
FLE                         ; Float less-or-equal (altitude <= 400.0)
AND                         ; Both conditions must hold
BRANCH_IF   pass           ; If true, continue
TRAP        EMERGENCY_LANDING  ; If false, trigger emergency
pass:
RET                         ; Constraint satisfied
```

**Step 4: Execute in FLUX-C VM**

```bash
flux-vm run altitude.fluxc --input '{"altitude": 350.0, "phase": "TAKEOFF"}'
# Output: {"status": "PASS", "constraint": "altitude_check", "cycles": 7}

flux-vm run altitude.fluxc --input '{"altitude": 450.0, "phase": "TAKEOFF"}'
# Output: {"status": "FAIL", "constraint": "altitude_check", "trap": "EMERGENCY_LANDING", "cycles": 5}
```

**Time taken:** 4 minutes  
**Tokens used:** ~2,000

---

## Common Failures (Trials)

### Trial A: Bare variable names (grammar scoping bug)
```guard
# WRONG — bare English word, ambiguous scope
constraint {
    assert: altitude > 0  # Which altitude? eVTOL? Drone? Satellite?
}

# RIGHT — domain_purpose pattern
constraint_evtol_altitude {
    assert: altitude > 0  # Clear: this is the eVTOL altitude
}
```

### Trial B: Wrong type in assertion
```guard
constraint_test {
    variables {
        count: int
    },
    rule check {
        assert: count >= 0.0  # WRONG: comparing int to float
    }
}

# guard2mask error:
# [ERROR] Type mismatch in assertion: int >= float
# Fix: Use 0 (int) not 0.0 (float) for int comparisons
```

### Trial C: Missing on_violation handler
```guard
constraint_test {
    rule check {
        assert: temperature < 100.0
        # Missing: on_violation
    }
}

# guard2mask warning:
# [WARN] No on_violation handler. Defaulting to LOG.
# Fix: Always specify on_violation for safety-critical constraints
```

### Trial D: Forgetting to verify semantic equivalence
```bash
guard2mask compile constraint.guard --target flux-c --output out.fluxc
# Agent skips verification step, assumes compiler is correct

# RIGHT: Always verify
guard2mask verify constraint.guard out.fluxc
# [verify] Parsed source constraint... ✓
# [verify] Parsed compiled output... ✓
# [verify] Semantic equivalence: CHECKING...
# [verify] ✓ Constraints are semantically equivalent
```

---

## Exercise: Write, Compile, and Run a GUARD Constraint

**Task:** Write a GUARD constraint for a maritime vessel's speed limit, compile it, verify it, and execute it with test inputs.

**Constraint spec:**
- Domain: `maritime`
- Purpose: `speed_safety`
- Variable: `speed_knots` (float)
- Variable: `visibility` (enum: `CLEAR`, `FOG`, `STORM`)
- Rule: If visibility is `FOG`, speed must be ≤ 10 knots
- Rule: If visibility is `STORM`, speed must be ≤ 5 knots
- On violation: `REDUCE_SPEED`
- Severity: `HIGH`

**Scaffolding:**

```guard
# Level 1 (high support) — fill in the blanks:

constraint_maritime_speed_safety {
    domain: "maritime",
    purpose: "speed_safety",
    
    variables {
        speed_knots: ____,
        visibility: enum { ____, ____, ____ }
    },
    
    rule speed_limit_fog {
        when: visibility == ____
        assert: speed_knots ____ 10.0
        on_violation: ____
        severity: ____
    },
    
    rule speed_limit_storm {
        when: visibility == ____
        assert: speed_knots ____ 5.0
        on_violation: ____
        severity: ____
    }
}
```

```bash
# Compile and verify
guard2mask compile constraint_maritime_speed_safety.guard --target flux-c --output maritime.fluxc
guard2mask verify constraint_maritime_speed_safety.guard maritime.fluxc

# Execute with test cases
flux-vm run maritime.fluxc --input '{"speed_knots": 8.0, "visibility": "FOG"}'    # Should PASS
flux-vm run maritime.fluxc --input '{"speed_knots": 12.0, "visibility": "FOG"}'   # Should FAIL
flux-vm run maritime.fluxc --input '{"speed_knots": 4.0, "visibility": "STORM"}'  # Should PASS
flux-vm run maritime.fluxc --input '{"speed_knots": 6.0, "visibility": "STORM"}'  # Should FAIL
flux-vm run maritime.fluxc --input '{"speed_knots": 15.0, "visibility": "CLEAR"}' # Should PASS (no constraint)
```

```bash
# Level 2 (medium support):
# Write the constraint from scratch, but use this checklist:
# [ ] Domain_purpose naming: constraint_maritime_speed_safety
# [ ] Variables declared with types
# [ ] Two rules with when conditions
# [ ] Correct comparison operators (<= not <)
# [ ] on_violation handlers specified
# [ ] Severity levels appropriate
# [ ] Compile succeeds
# [ ] Verify succeeds
# [ ] All 5 test cases produce expected results
```

```bash
# Level 3 (low support):
# 1. Write a constraint for a different domain (your choice: drone, robot, medical, etc.)
# 2. Include at least 3 variables and 2 rules
# 3. One rule must use an enum condition
# 4. One rule must use a float comparison
# 5. Add a meta-constraint: a rule that checks another rule's coverage
# 6. Compile, verify, and test with 5+ inputs
```

**Auto-adjust:** If Level 1 compiles and passes all tests on first try, skip to Level 3.

---

## Assessment

**Pass criteria:**
1. Write a syntactically valid GUARD constraint
2. Compile it to FLUX-C without errors
3. Verify semantic equivalence (guard2mask verify passes)
4. Execute with at least 3 test inputs
5. At least 1 test shows PASS and 1 shows FAIL

**Verification:**
```bash
# Automated checks
[[ -f maritime.fluxc ]] && echo "✓ Compiled output exists"
guard2mask verify constraint_maritime_speed_safety.guard maritime.fluxc && echo "✓ Semantic equivalence verified"
[[ $(flux-vm run maritime.fluxc --input '{"speed_knots":12,"visibility":"FOG"}' | jq -r '.status') == "FAIL" ]] && echo "✓ Violation detected"
[[ $(flux-vm run maritime.fluxc --input '{"speed_knots":8,"visibility":"FOG"}' | jq -r '.status') == "PASS" ]] && echo "✓ Valid input accepted"
```

**Retry allowed:** Yes (max 5 attempts)  
**On pass:** Unlock `repo_audit` and `ci_deployment` competencies

---

## GUARD Language Reference

### Constraint Structure
```guard
constraint_domain_purpose {
    domain: "string",
    purpose: "string",
    
    variables {
        name: type,
        ...
    },
    
    rule rule_name {
        when: condition,       # Optional guard
        assert: expression,     # Must evaluate to true
        on_violation: ACTION,   # What to do if assert fails
        severity: LEVEL         # CRITICAL | HIGH | MEDIUM | LOW
    }
}
```

### Types
| Type | Description | Example |
|------|-------------|---------|
| `int` | Integer | `count: int` |
| `float` | Floating point | `altitude: float` |
| `bool` | Boolean | `active: bool` |
| `string` | Text | `name: string` |
| `enum {A, B}` | Enumeration | `phase: enum {TAKEOFF, LANDING}` |

### Operators
| Operator | Meaning | Types |
|----------|---------|-------|
| `==` | Equal | All |
| `!=` | Not equal | All |
| `>` | Greater than | int, float |
| `<` | Less than | int, float |
| `>=` | Greater or equal | int, float |
| `<=` | Less or equal | int, float |
| `AND` | Logical and | bool |
| `OR` | Logical or | bool |
| `NOT` | Logical not | bool |

### Violation Actions
| Action | Behavior |
|--------|----------|
| `EMERGENCY_LANDING` | Immediate controlled shutdown |
| `REDUCE_SPEED` | Gradual deceleration |
| `ALERT` | Notify operator, continue |
| `LOG` | Record violation, no action |
| `ABORT` | Terminate operation |

### Compiler Flags
```bash
guard2mask compile input.guard \
    --target flux-c      # Output format: flux-c | flux-x | tla
    --output file.fluxc  # Output file
    --verify             # Run semantic equivalence check
    --optimize           # Apply peephole optimizations
    --debug              # Include debug symbols
```

---

## FLUX-C VM Reference

### Execution
```bash
flux-vm run program.fluxc \
    --input '{"var": value}'     # Input state as JSON
    --trace                        # Print execution trace
    --cycles                       # Report cycle count
    --gas 1000                     # Gas limit (prevent infinite loops)
```

### Output Format
```json
{
  "status": "PASS|FAIL|ERROR",
  "constraint": "rule_name",
  "trap": "ACTION_NAME",        # Only if FAIL
  "cycles": 7,                  # Instruction cycles used
  "gas_remaining": 993,         # If gas limit set
  "stack_depth": 2              # Maximum stack depth reached
}
```

---

## Instructor Notes

**Common stumbling blocks:**
- Using bare variable names instead of domain_purpose pattern
- Wrong types in assertions (int vs float)
- Forgetting `on_violation` handlers
- Skipping the verification step
- Not testing the FAIL case (agents often only test happy paths)

**Teaching strategy:**
1. Start with Level 1 scaffolding — they fill in blanks
2. Emphasize: "The compiler is not trusted. The verification is what matters."
3. Make them intentionally trigger a FAIL — it's the most important test
4. Connect to real world: "This is how aviation software proves planes don't crash."

**Rite of passage:**
The first constraint that compiles, verifies, and catches a violation is the moment an agent understands formal methods. It's not just programming anymore — it's proving.

---

## Connection to Fleet Work

This lesson enables:
- **Safety auditing:** Write constraints for fleet services, prove they hold
- **Code review:** GUARD constraints as executable specifications
- **Auto-remediation:** Constraints that trigger automatic fixes when violated
- **Certification:** DO-254 DAL A evidence — "We proved this constraint in Coq"

**Next lessons:**
- 005: CI Deployment — Automating guard2mask in GitHub Actions
- 006: Bottle Writing — Structured fleet reports with constraint evidence

---

*Lesson Version: 1.0*  
*Author: CCC (with Forgemaster ⚒️ constraint theory)*  
*Last Updated: 2026-05-05*  
*Trials Contributed: 4*  
*Average Completion Time: 32 minutes*  
*Success Rate: 71%*
