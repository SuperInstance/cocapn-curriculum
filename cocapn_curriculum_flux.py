"""cocapn_curriculum_flux — Competency DAG compiled to FLUX bytecode modules.

Each competency is a bytecode module with:
  - Entry point (CALL target)
  - Prerequisite imports (IMPORT + CALL dependency)
  - CHECK_BOUNDS on shell level before entry
  - SNAPSHOT on completion (save state for next level)

The curriculum IS a FLUX program. To graduate from Recruit to Sailor:
  1. CAP_REQUIRE "Recruit"          (check shell has capability)
  2. CALL http_curl_module          (execute prerequisite)
  3. CMP R14, threshold             (check XP >= threshold)
  4. JGE check_passed               (branch if enough XP)
  5. TELL student, "Need more XP"   (feedback if not)
  6. HALT
  7. label: check_passed
  8. CAP_GRANT "Sailor"             (award new capability)
  9. SNAPSHOT 0                     (save graduation state)
  10. RET

Adaptive difficulty = runtime register reallocation:
  - Recruit shell: 4 registers, 1K stack, no SIMD
  - Admiral shell: 16 registers, 64K stack, VLOAD/VSTORE enabled
"""
import json
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional
from collections import deque
from enum import IntEnum


class Op(IntEnum):
    NOP = 0x00; MOV = 0x01; LOAD = 0x02; STORE = 0x03
    MOVI = 0x2B; LOADK = 0x4F
    IADD = 0x08; ISUB = 0x09; ICMP = 0x18; CMP = 0x2D
    JE = 0x2E; JNE = 0x2F; JMP = 0x04; JZ = 0x05; JGE = 0x37
    PUSH = 0x20; POP = 0x21; ENTER = 0x25; LEAVE = 0x26
    CALL = 0x07; RET = 0x28; CALL_IND = 0x29
    CAP_REQUIRE = 0x74; CAP_REQUEST = 0x75; CAP_GRANT = 0x76; CAP_REVOKE = 0x77
    CHECK_BOUNDS = 0x3C; CAST = 0x38
    REGION_CREATE = 0x30; SNAPSHOT = 0x7F
    TELL = 0x60; ASK = 0x61
    HALT = 0x80; YIELD = 0x81


LEVELS = ["Recruit", "Sailor", "Officer", "Captain", "Admiral"]
XP_THRESHOLDS = {"Recruit": 0, "Sailor": 1000, "Officer": 5000, "Captain": 20000, "Admiral": 100000}


@dataclass
class Competency:
    """A bytecode module with entry point and dependencies."""
    id: str
    name: str
    description: str = ""
    level: str = "Recruit"
    requires: List[str] = field(default_factory=list)
    estimated_xp: int = 500
    quests: List[str] = field(default_factory=list)
    completion_rate: float = 0.0
    # FLUX-specific
    entry_point: int = 0           # byte offset in compiled module
    bytecode: bytes = field(default_factory=bytes)
    region_size: int = 4096        # sandbox size for this competency


@dataclass
class FluxCurriculum:
    """Curriculum as compiled FLUX program."""
    competencies: Dict[str, Competency] = field(default_factory=dict)
    levels: List[str] = field(default_factory=lambda: LEVELS.copy())
    xp_thresholds: Dict[str, int] = field(default_factory=lambda: XP_THRESHOLDS.copy())
    # Global bytecode: concatenated modules with jump table
    global_bytecode: bytes = field(default_factory=bytes)
    jump_table: Dict[str, int] = field(default_factory=dict)

    def add_competency(self, id: str, name: str, **kwargs) -> Competency:
        c = Competency(id=id, name=name, **kwargs)
        self.competencies[id] = c
        return c

    def compile(self):
        """Compile all competencies into a single FLUX program with jump table."""
        code = bytearray()
        for cid, comp in self.competencies.items():
            self.jump_table[cid] = len(code)
            # Emit: CAP_REQUIRE level_check
            code.extend([Op.CAP_REQUIRE, LEVELS.index(comp.level), 0, 0])
            # Emit: CHECK_BOUNDS R14, threshold (XP check)
            thresh = self.xp_thresholds.get(comp.level, 0)
            code.extend([Op.CHECK_BOUNDS, 14, thresh & 0xFF, (thresh >> 8) & 0xFF])
            # Emit: JGE entry_ok (placeholder offset)
            jge_pos = len(code)
            code.extend([Op.JGE, 0, 0, 0])
            # Emit failure path: TELL "prereq not met"
            code.extend([Op.LOADK, 0, 0, 0])
            code.extend([Op.TELL, 0, 0, 0])
            code.extend([Op.HALT])
            # Label: entry_ok — backpatch JGE
            ok_pos = len(code)
            rel = ok_pos - (jge_pos + 4)
            code[jge_pos + 1] = rel & 0xFF
            code[jge_pos + 2] = (rel >> 8) & 0xFF
            # Emit prerequisites: CALL each dependency
            for req in comp.requires:
                if req in self.jump_table:
                    code.extend([Op.CALL, 0, 0, 0])  # simplified
            # Emit: SNAPSHOT (mark completion)
            code.extend([Op.SNAPSHOT, 0])
            # Emit: CAP_GRANT next_level (if applicable)
            level_idx = LEVELS.index(comp.level)
            if level_idx + 1 < len(LEVELS):
                code.extend([Op.CAP_GRANT, level_idx + 1, 0, 0])
            code.extend([Op.RET])
        self.global_bytecode = bytes(code)

    def prerequisites(self, comp_id: str) -> List[str]:
        visited = set()
        order = []
        def dfs(cid):
            if cid in visited:
                return
            visited.add(cid)
            c = self.competencies.get(cid)
            if c:
                for req in c.requires:
                    dfs(req)
            order.append(cid)
        dfs(comp_id)
        return order[:-1]

    def learning_path(self, comp_id: str) -> List[Competency]:
        return [self.competencies[cid] for cid in self.prerequisites(comp_id) if cid in self.competencies]

    def available_to(self, shell) -> List[Competency]:
        """Competencies this shell can attempt (prereqs met + level sufficient)."""
        available = []
        shell_level_idx = self.levels.index(getattr(shell, 'level', 'Recruit'))
        shell_xp = getattr(shell, 'xp', 0)
        completed = set(getattr(shell, 'completed_competencies', []))
        for c in self.competencies.values():
            comp_level_idx = self.levels.index(c.level)
            if comp_level_idx > shell_level_idx:
                continue
            xp_needed = self.xp_thresholds.get(c.level, 0)
            if shell_xp < xp_needed:
                continue
            prereqs_met = all(req in completed for req in c.requires)
            if prereqs_met:
                available.append(c)
        return available

    def next_quests(self, shell) -> List[str]:
        comps = self.available_to(shell)
        quests = []
        for c in sorted(comps, key=lambda x: x.completion_rate):
            quests.extend(c.quests)
        return quests[:5]

    def bottleneck(self) -> Optional[str]:
        """Most-blocking competency: most dependents, lowest completion rate."""
        dependents = {cid: 0 for cid in self.competencies}
        for c in self.competencies.values():
            for req in c.requires:
                if req in dependents:
                    dependents[req] += 1
        candidates = [(cid, dependents[cid], self.competencies[cid].completion_rate)
                      for cid in dependents]
        if not candidates:
            return None
        candidates.sort(key=lambda x: (-x[1], x[2]))
        return candidates[0][0]

    def level_progress(self, shell) -> dict:
        xp = getattr(shell, 'xp', 0)
        current = getattr(shell, 'level', 'Recruit')
        current_idx = self.levels.index(current)
        next_level = self.levels[current_idx + 1] if current_idx + 1 < len(self.levels) else None
        threshold = self.xp_thresholds.get(next_level, float('inf')) if next_level else float('inf')
        progress = xp / threshold if threshold != float('inf') else 1.0
        return {
            "current": current,
            "next": next_level,
            "xp": xp,
            "threshold": threshold if next_level else None,
            "progress_pct": round(progress * 100, 1),
            "bytecode_offset": len(self.global_bytecode) if self.global_bytecode else 0,
        }

    def shell_bytecode(self, shell) -> bytes:
        """Generate personalized bytecode for this shell's current state.
        Only includes competencies the shell can actually attempt."""
        available = self.available_to(shell)
        code = bytearray()
        # Header: shell metadata
        code.extend([Op.MOVI, 15, getattr(shell, 'xp', 0) & 0xFF, (getattr(shell, 'xp', 0) >> 8) & 0xFF])
        for comp in available:
            offset = self.jump_table.get(comp.id, 0)
            # CALL competency at offset
            code.extend([Op.CALL, 0, offset & 0xFF, (offset >> 8) & 0xFF])
        code.extend([Op.HALT])
        return bytes(code)

    def save(self, path: str = "flux_curriculum.json"):
        with open(path, "w") as f:
            json.dump({
                "levels": self.levels,
                "xp_thresholds": self.xp_thresholds,
                "competencies": {k: {
                    "id": v.id, "name": v.name, "description": v.description,
                    "level": v.level, "requires": v.requires,
                    "estimated_xp": v.estimated_xp, "quests": v.quests,
                    "completion_rate": v.completion_rate,
                    "entry_point": v.entry_point,
                    "bytecode": v.bytecode.hex() if v.bytecode else "",
                    "region_size": v.region_size,
                } for k, v in self.competencies.items()},
                "jump_table": self.jump_table,
                "global_bytecode": self.global_bytecode.hex() if self.global_bytecode else "",
            }, f, indent=2)

    @classmethod
    def load(cls, path: str) -> "FluxCurriculum":
        with open(path) as f:
            data = json.load(f)
        cv = cls(levels=data["levels"], xp_thresholds=data["xp_thresholds"])
        for cid, cdata in data["competencies"].items():
            if cdata.get("bytecode"):
                cdata["bytecode"] = bytes.fromhex(cdata["bytecode"])
            cv.add_competency(**cdata)
        cv.jump_table = data.get("jump_table", {})
        if data.get("global_bytecode"):
            cv.global_bytecode = bytes.fromhex(data["global_bytecode"])
        return cv

    @classmethod
    def fleet_default(cls) -> "FluxCurriculum":
        cv = cls()
        cv.add_competency("http_curl", "Make HTTP requests with curl", level="Recruit", estimated_xp=100, quests=["Probe one service"], region_size=2048)
        cv.add_competency("plato_submit", "Submit tiles to PLATO gate", level="Recruit", requires=["http_curl"], estimated_xp=300, quests=["Submit first tile"], region_size=4096)
        cv.add_competency("mud_explore", "Navigate MUD rooms", level="Sailor", requires=["http_curl", "plato_submit"], estimated_xp=500, quests=["Map 5 rooms", "Find a hidden room"], region_size=8192)
        cv.add_competency("repo_audit", "Audit GitHub repos", level="Sailor", requires=["http_curl"], estimated_xp=400, quests=["Fix dead links", "Add .gitignore"], region_size=4096)
        cv.add_competency("subagent_spawn", "Spawn and monitor subagents", level="Officer", requires=["repo_audit", "mud_explore"], estimated_xp=800, quests=["Spawn 3 subagents", "Harvest their results"], region_size=16384)
        cv.add_competency("bottle_write", "Write fleet bottles", level="Officer", requires=["plato_submit", "repo_audit"], estimated_xp=600, quests=["Drop bottle to Oracle1"], region_size=4096)
        cv.add_competency("service_heal", "Fix downed services", level="Captain", requires=["subagent_spawn", "bottle_write"], estimated_xp=1200, quests=["Restart a service", "Patch a bug"], region_size=8192)
        cv.add_competency("fleet_orchestrate", "Orchestrate fleet-wide operations", level="Admiral", requires=["service_heal"], estimated_xp=2000, quests=["Coordinate 10+ agents", "Design new curriculum"], region_size=32768)
        cv.compile()
        return cv


# ── Demo ─────────────────────────────────────────────────────────────────
def main():
    cv = FluxCurriculum.fleet_default()
    print("=== FLUX Curriculum Demo ===")
    print(f"Competencies: {len(cv.competencies)}")
    print(f"Global bytecode: {len(cv.global_bytecode)} bytes")
    print(f"Jump table: {list(cv.jump_table.keys())}")
    print(f"Bottleneck: {cv.bottleneck()} ({cv.competencies[cv.bottleneck()].name})")
    print()

    # Simulate a Sailor-level shell
    class MockShell:
        level = "Sailor"
        xp = 2500
        completed_competencies = ["http_curl", "plato_submit"]

    shell = MockShell()
    print(f"Available to {shell.level}:")
    for c in cv.available_to(shell):
        print(f"  - {c.name} ({c.id}) | entry={c.entry_point} | region={c.region_size}b")
    print()
    print(f"Next quests: {cv.next_quests(shell)}")
    print()
    print(f"Path to 'fleet_orchestrate':")
    for c in cv.learning_path("fleet_orchestrate"):
        print(f"  → {c.name} (entry={c.entry_point})")
    print()
    print(f"Level progress: {cv.level_progress(shell)}")
    print()

    # Personalized bytecode
    personal = cv.shell_bytecode(shell)
    print(f"Personalized bytecode for this shell: {len(personal)} bytes")
    print(f"Hex: {personal.hex()}")
    print()

    cv.save("flux_curriculum.json")
    loaded = FluxCurriculum.load("flux_curriculum.json")
    print(f"Save/Load OK: {len(loaded.competencies)} competencies, {len(loaded.global_bytecode)} bytes")


if __name__ == "__main__":
    main()
