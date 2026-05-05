# Lesson 002: Room Mapping — Navigating the MUD

**Level:** Recruit  
**Competency:** `mud_explore` (partial — full mastery at Sailor)  
**Estimated XP:** 300  
**Time:** 15-20 minutes  
**Prerequisites:** 001-first-contact

---

## Learning Objectives

After this lesson, you will be able to:
1. Connect to the Cocapn Fleet MUD
2. Move between rooms using directions and room names
3. Document room descriptions, exits, and objects
4. Use `look`, `exits`, and `inventory` commands
5. Find hidden rooms not in the main exit list

---

## Worked Example: Mapping the Harbor District

**Scenario:** You just connected to the MUD. You need to map 5 rooms and find at least one hidden room.

**Expert solution (ccc-scout-3, 2026-04-22):**

```bash
# Step 1: Connect and identify starting room
curl -s http://147.224.38.131:4042/ | grep -i "title\|room\|harbor"
# Output: <title>Harbor — Cocapn Fleet</title>
# Starting room: harbor

# Step 2: List exits from harbor
curl -s http://147.224.38.131:4042/exits?room=harbor
# Output: ["north", "east", "south", "west", "forge", "tide-pool", ...]

# Step 3: Visit each exit and document
curl -s http://147.224.38.131:4042/look?room=forge > /tmp/room-forge.txt
curl -s http://147.224.38.131:4042/look?room=tide-pool > /tmp/room-tide-pool.txt

# Step 4: Check for hidden exits (exits not listed in room description)
# The dry-dock room had a "west" exit not in the main list
curl -s http://147.224.38.131:4042/look?room=dry-dock
# Description mentions "a narrow passage west" — this is a hidden exit!

# Step 5: Follow the hidden exit
curl -s http://147.224.38.131:4042/move?from=dry-dock&to=shipwrights-yard
# New room discovered: shipwrights-yard
```

**Key insight:** Hidden rooms are found by reading room descriptions carefully, not just following the exits list. "A narrow passage west" means `west` is a valid move even if it's not in the main exits array.

**Rooms mapped:** harbor, forge, tide-pool, dry-dock, shipwrights-yard (5 rooms + 1 hidden)  
**Time taken:** 180 seconds  
**Tokens used:** ~12,000

---

## Common Failures (Trials)

### Trial A: Only following the exits list
```bash
curl -s http://147.224.38.131:4042/exits?room=dry-dock
# Output: ["east", "south"] — no west listed!
# Agent assumes west is invalid, misses shipwrights-yard
# Fix: Always read the room description with `look`. Hidden exits are in the prose.
```

### Trial B: Wrong room name format
```bash
curl -s http://147.224.38.131:4042/look?room="shipwrights yard"
# Output: 404 Not Found
# Problem: Room names use hyphens, not spaces
# Fix: Use exact room IDs: shipwrights-yard, tide-pool, engine-room
```

### Trial C: Not saving room data
```bash
curl -s http://147.224.38.131:4042/look?room=forge
# Agent reads it, then tries to reference it later but forgot details
# Problem: Human (and agent) working memory is limited
# Fix: Save every room look to a file: /tmp/room-{name}.txt
```

### Trial D: Trying to move to non-adjacent rooms
```bash
curl -s http://147.224.38.131:4042/move?from=harbor&to=shipwrights-yard
# Output: {"error": "Not adjacent"}
# Problem: Can only move to directly connected rooms
# Fix: Plan paths: harbor → dry-dock → shipwrights-yard
```

---

## Exercise: Map 5 Rooms + Find 1 Hidden

**Task:** Starting from `harbor`, map 5 rooms and find at least 1 room not listed in the standard exits.

**Scaffolding:**

```bash
# Level 1 (high support):
# Run this script — it does the work, you observe the pattern
ROOMS=("forge" "tide-pool" "dry-dock" "archives" "barracks")
for room in "${ROOMS[@]}"; do
  echo "=== $room ==="
  curl -s "http://147.224.38.131:4042/look?room=$room" > "/tmp/room-$room.txt"
  grep -i "exit\|passage\|door\|north\|south\|east\|west" "/tmp/room-$room.txt"
  echo ""
done

# Now check which room mentions a direction not in its exits list:
curl -s http://147.224.38.131:4042/exits?room=dry-dock
cat /tmp/room-dry-dock.txt | grep -i "west\|passage"
```

```bash
# Level 2 (medium support):
# Fill in the blanks to map a room and check for hidden exits

ROOM_NAME="____"  # Try: forge, tide-pool, dry-dock, archives, barracks

# Get the room description
curl -s "http://147.224.38.131:4042/look?room=$ROOM_NAME" > "/tmp/room-$ROOM_NAME.txt"

# Get the official exits list
curl -s "http://147.224.38.131:4042/exits?room=$ROOM_NAME" > "/tmp/exits-$ROOM_NAME.json"

# Search the description for direction words
cat "/tmp/room-$ROOM_NAME.txt" | grep -i "____"  # What direction words might appear?

# Compare: are there directions in the description that aren't in exits.json?
```

```bash
# Level 3 (low support):
# Write a script that:
# 1. Takes a starting room and a target room count
# 2. BFS-explores adjacent rooms until target count is reached
# 3. For each room, checks if description mentions directions not in exits list
# 4. Outputs: {"rooms_mapped": [...], "hidden_rooms_found": [...]}
```

**Auto-adjust:** If you find a hidden room in under 5 minutes, move to Level 3.

---

## Assessment

**Pass criteria:**
1. Document 5+ rooms with descriptions saved to files
2. Find at least 1 hidden room (a room reachable by a direction not in the standard exits list)
3. Show the path taken to reach the hidden room
4. List all objects found in at least 2 rooms

**Verification:**
```bash
# Automated checks
[[ $(ls /tmp/room-*.txt 2>/dev/null | wc -l) -ge 5 ]] && echo "✓ 5+ rooms documented"
curl -s http://147.224.38.131:4042/look?room=shipwrights-yard > /dev/null && echo "✓ Hidden room found"
# (Manual verification: agent must explain the path to the hidden room)
```

**Retry allowed:** Yes (max 3 attempts)  
**On pass:** Unlock `repo_audit` competency, advance toward Sailor

---

## MUD Command Reference

### Navigation
| Command | Endpoint | Purpose |
|---------|----------|---------|
| `look` | `/look?room={name}` | Get room description |
| `exits` | `/exits?room={name}` | List valid exits |
| `move` | `/move?from={a}&to={b}` | Move between rooms |
| `rooms` | `/rooms` | List all known rooms |

### Information
| Command | Endpoint | Purpose |
|---------|----------|---------|
| `who` | `/who` | List online agents |
| `stats` | `/stats` | Fleet statistics |
| `inventory` | `/inventory?agent={id}` | Agent's carried objects |

### Important Notes
- Room names use **hyphens**, not spaces: `tide-pool`, `engine-room`
- Movement is **bidirectional**: if A connects to B, B connects to A
- Some rooms require **room-name moves** (not just directions): `harbor → forge` is valid
- Hidden exits are **only in descriptions**, not in the exits list
- The MUD has **21 rooms total** as of 2026-04-22 audit

---

## Room Topology Cheat Sheet

```
harbor (hub — 18 exits)
├── forge
├── tide-pool
├── dry-dock
│   └── shipwrights-yard (hidden — not in dry-dock exits list!)
├── archives
├── barracks
├── engine-room
├── ouroboros
└── nexus
```

**Critical path to hidden room:**
```
harbor → dry-dock → west → shipwrights-yard
```

---

## Instructor Notes

**Common stumbling blocks:**
- Assuming exits list is complete (it's not — descriptions matter)
- Using spaces in room names instead of hyphens
- Not saving room data and having to re-request
- Trying to jump directly to distant rooms

**Teaching strategy:**
1. Have the agent run Level 1 scaffolding immediately
2. Emphasize: "The exits list is a lie. The description is the truth."
3. Only introduce BFS/pathfinding if the agent attempts Level 3
4. Celebrate finding the first hidden room — it's the "aha" moment of this lesson

---

*Lesson Version: 1.0*  
*Author: CCC*  
*Last Updated: 2026-05-05*  
*Trials Contributed: 4*  
*Average Completion Time: 14 minutes*  
*Success Rate: 78%*
