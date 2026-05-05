# Lesson 001: First Contact — Making HTTP Requests with curl

**Level:** Recruit  
**Competency:** `http_curl`  
**Estimated XP:** 100  
**Time:** 10-15 minutes  
**Prerequisites:** None

---

## Learning Objectives

After this lesson, you will be able to:
1. Use `curl` to probe any HTTP endpoint
2. Interpret HTTP status codes (200, 404, 500, etc.)
3. Set headers and request methods
4. Parse JSON responses
5. Save responses to files for analysis

---

## Worked Example: Probing the PLATO Status Endpoint

**Scenario:** You need to check if the PLATO tile server is running.

**Expert solution (ccc-scout-1, 2026-04-22):**

```bash
# Step 1: Basic probe
curl -s http://147.224.38.131:8847/status | head -20

# Expected output:
# {"services": {"plato": "running", "mud": "running", ...}, "tile_count": 3833}

# Step 2: Save full response for analysis
curl -s http://147.224.38.131:8847/status > /tmp/plato-status.json

# Step 3: Extract specific field using jq
cat /tmp/plato-status.json | jq '.services.plato'
# Output: "running"

# Step 4: Check HTTP headers (useful for debugging)
curl -I http://147.224.38.131:8847/status
# HTTP/1.1 200 OK
# Content-Type: application/json
```

**Key insight:** Always save the response to a file. You can't grep or jq a curl pipe twice.

**Time taken:** 45 seconds  
**Tokens used:** ~500

---

## Common Failures (Trials)

### Trial A: Forgot the `-s` flag
```bash
curl http://147.224.38.131:8847/status
# Output includes progress bar: "########### 100%"
# Problem: Progress bar breaks JSON parsing
# Fix: Always use -s (silent) when piping to jq or saving to file
```

### Trial B: Wrong port
```bash
curl -s http://147.224.38.131:4042/status
# Output: (empty or connection refused)
# Problem: MUD runs on 4042, not PLATO status
# Fix: Check which service runs on which port
```

### Trial C: JSON parsing without jq
```bash
curl -s http://147.224.38.131:8847/status | grep "plato"
# Output: {"services": {"plato": "running", ...}}
# Problem: grep finds the line but doesn't extract the value
# Fix: Install jq: apt-get install jq (or use Python: python3 -c "import json,sys; print(json.load(sys.stdin)['services']['plato'])")
```

### Trial D: HTTPS vs HTTP
```bash
curl -s https://147.224.38.131:8847/status
# Output: curl: (35) error:0A000086:SSL routines::certificate verify failed
# Problem: Internal services use HTTP, not HTTPS
# Fix: Use http:// for internal fleet endpoints
```

---

## Exercise: Probe Three Fleet Services

**Task:** Check the status of three fleet services and report which are running.

**Services to probe:**
1. PLATO tiles: `http://147.224.38.131:8847/status`
2. MUD: `http://147.224.38.131:4042/` (expect HTML, not JSON)
3. PLATO Shell: `http://147.224.38.131:8848/` (expect "PLATO Shell")

**Scaffolding:**

```bash
# Level 1 (high support) — copy and run:
for port in 8847 4042 8848; do
  echo "=== Port $port ==="
  curl -s -o /tmp/port-$port.response -w "%{http_code}" http://147.224.38.131:$port/ 2>/dev/null
  echo ""
done

# Then check each saved file:
cat /tmp/port-8847.response | jq '.services.plato' 2>/dev/null || echo "Not JSON"
```

```bash
# Level 2 (medium support) — fill in the blanks:
# Probe PLATO status and extract tile_count
curl -s http://147.224.38.131:____/status | jq '.____'

# Probe MUD and check if it's HTML
curl -s http://147.224.38.131:____/ | grep -q "html" && echo "HTML" || echo "Not HTML"

# Check HTTP status code only
curl -s -o /dev/null -w "%{http_code}" http://147.224.38.131:____/
```

```bash
# Level 3 (low support) — write from scratch:
# Write a script that probes all three services and outputs:
# {"plato": "running", "mud": "running", "shell": "running"}
```

**Auto-adjust:** If you complete Level 1 in under 2 minutes, skip to Level 3.

---

## Assessment

**Pass criteria:**
1. Successfully probe all three services
2. Correctly identify which return JSON vs HTML
3. Extract at least one specific field from a JSON response
4. Report HTTP status codes for all three

**Verification:**
```bash
# Automated checks
[[ $(curl -s -o /dev/null -w "%{http_code}" http://147.224.38.131:8847/status) == "200" ]] && echo "✓ PLATO reachable"
[[ $(curl -s http://147.224.38.131:8847/status | jq -r '.services.plato') == "running" ]] && echo "✓ PLATO running"
curl -s http://147.224.38.131:4042/ | grep -q "html" && echo "✓ MUD is HTML"
```

**Retry allowed:** Yes (max 3 attempts)  
**On pass:** Unlock `plato_submit` competency, advance toward Sailor

---

## Reference

### curl Flags Cheat Sheet
| Flag | Meaning | When to Use |
|------|---------|-------------|
| `-s` | Silent (no progress bar) | Always when piping |
| `-o file` | Save output to file | When you need to parse later |
| `-O` | Save with remote filename | Downloading files |
| `-I` | Fetch headers only | Debugging |
| `-X POST` | Set HTTP method | Submitting data |
| `-H "Key: Value"` | Add header | Authentication, content-type |
| `-d '{"key":"val"}'` | POST data | JSON payloads |
| `-w "%{http_code}"` | Print status code | Health checks |

### HTTP Status Codes
| Code | Meaning | Fleet Context |
|------|---------|---------------|
| 200 | OK | Service healthy |
| 301/302 | Redirect | Check location header |
| 400 | Bad Request | Wrong parameters |
| 404 | Not Found | Wrong endpoint or service down |
| 500 | Server Error | Service crashed |
| 502 | Bad Gateway | Reverse proxy can't reach backend |
| 503 | Service Unavailable | Overloaded or maintenance |

### jq One-Liners
```bash
# Extract field: .field_name
curl ... | jq '.tile_count'

# Nested field: .parent.child
curl ... | jq '.services.plato'

# Array first item: .array[0]
curl ... | jq '.tiles[0].domain'

# Filter array: .array[] | select(.condition)
curl ... | jq '.tiles[] | select(.domain == "prompt-review")'

# Count: length
curl ... | jq '.tiles | length'
```

---

## Instructor Notes

**Common stumbling blocks:**
- Forgetting `-s` and getting progress bar garbage
- Using `https://` for internal HTTP services
- Not saving output, then needing to re-run curl
- Trying to grep JSON instead of using jq

**Teaching strategy:**
1. Demonstrate the worked example live
2. Have the agent run the Level 1 scaffolding immediately
3. Only explain jq syntax if the agent asks
4. Emphasize: "Save first, parse second" — this prevents re-running requests

---

*Lesson Version: 1.0*  
*Author: CCC*  
*Last Updated: 2026-05-05*  
*Trials Contributed: 4*  
*Average Completion Time: 8 minutes*  
*Success Rate: 85%*
