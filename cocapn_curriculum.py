"""cocapn_curriculum — Five-level curriculum with competency DAG.

Levels: Recruit → Sailor → Officer → Captain → Admiral
Each level has formal prerequisites (competencies). The curriculum is a
directed acyclic graph where nodes are competencies and edges are
prerequisites. Adaptive difficulty means an agent only sees quests
it can actually complete.

Usage:
    cv = Curriculum()
    cv.add_competency("curl HTTP requests")
    cv.add_competency("PLATO tile submission", requires=["curl HTTP requests"])
    cv.add_competency("MUD room mapping", requires=["curl HTTP requests", "PLATO tile submission"])
    path = cv.learning_path("MUD room mapping")  # ordered prerequisites
"""
import json
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional
from collections import deque


@dataclass
class Competency:
    """A single skill or capability in the curriculum."""
    id: str
    name: str
    description: str = ""
    level: str = "Recruit"        # minimum fleet level to attempt
    requires: List[str] = field(default_factory=list)
    estimated_xp: int = 500       # XP awarded on completion
    quests: List[str] = field(default_factory=list)  # linked quest names
    completion_rate: float = 0.0  # historical success rate


@dataclass
class Curriculum:
    """Fleet curriculum as a DAG of competencies."""
    competencies: Dict[str, Competency] = field(default_factory=dict)
    levels: List[str] = field(default_factory=lambda: ["Recruit", "Sailor", "Officer", "Captain", "Admiral"])
    xp_thresholds: Dict[str, int] = field(default_factory=lambda: {
        "Recruit": 0, "Sailor": 1000, "Officer": 5000, "Captain": 20000, "Admiral": 100000
    })

    def add_competency(self, id: str, name: str, **kwargs) -> Competency:
        """Add a competency to the DAG."""
        c = Competency(id=id, name=name, **kwargs)
        self.competencies[id] = c
        return c

    def prerequisites(self, comp_id: str) -> List[str]:
        """All prerequisites (transitive) for a competency, topologically sorted."""
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
        return order[:-1]  # exclude comp_id itself

    def learning_path(self, comp_id: str) -> List[Competency]:
        """Ordered list of competencies to learn before target."""
        return [self.competencies[cid] for cid in self.prerequisites(comp_id) if cid in self.competencies]

    def available_to(self, shell) -> List[Competency]:
        """Competencies this shell can attempt (prereqs met + level sufficient)."""
        available = []
        shell_level_idx = self.levels.index(getattr(shell, 'level', 'Recruit'))
        for c in self.competencies.values():
            comp_level_idx = self.levels.index(c.level)
            if comp_level_idx > shell_level_idx:
                continue
            prereqs_met = all(req in getattr(shell, 'completed_competencies', []) for req in c.requires)
            if prereqs_met:
                available.append(c)
        return available

    def next_quests(self, shell) -> List[str]:
        """Quest names the shell should tackle next."""
        comps = self.available_to(shell)
        quests = []
        for c in sorted(comps, key=lambda x: x.completion_rate):
            quests.extend(c.quests)
        return quests[:5]  # top 5 recommendations

    def bottleneck(self) -> Optional[str]:
        """Most-blocking competency (most dependents, lowest completion rate)."""
        dependents = {cid: 0 for cid in self.competencies}
        for c in self.competencies.values():
            for req in c.requires:
                if req in dependents:
                    dependents[req] += 1
        candidates = [(cid, dependents[cid], self.competencies[cid].completion_rate)
                      for cid in dependents]
        if not candidates:
            return None
        # Most dependents, then lowest completion rate
        candidates.sort(key=lambda x: (-x[1], x[2]))
        return candidates[0][0]

    def level_progress(self, shell) -> dict:
        """Progress toward next level."""
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
        }

    def save(self, path: str = "curriculum.json"):
        with open(path, "w") as f:
            json.dump({
                "levels": self.levels,
                "xp_thresholds": self.xp_thresholds,
                "competencies": {k: {
                    "id": v.id, "name": v.name, "description": v.description,
                    "level": v.level, "requires": v.requires,
                    "estimated_xp": v.estimated_xp, "quests": v.quests,
                    "completion_rate": v.completion_rate,
                } for k, v in self.competencies.items()}
            }, f, indent=2)

    @classmethod
    def load(cls, path: str) -> "Curriculum":
        with open(path) as f:
            data = json.load(f)
        cv = cls(levels=data["levels"], xp_thresholds=data["xp_thresholds"])
        for cid, cdata in data["competencies"].items():
            cv.add_competency(**cdata)
        return cv

    @classmethod
    def fleet_default(cls) -> "Curriculum":
        """Build the default fleet curriculum."""
        cv = cls()
        cv.add_competency("http_curl", "Make HTTP requests with curl", level="Recruit", estimated_xp=100, quests=["Probe one service"])
        cv.add_competency("plato_submit", "Submit tiles to PLATO gate", level="Recruit", requires=["http_curl"], estimated_xp=300, quests=["Submit first tile"])
        cv.add_competency("mud_explore", "Navigate MUD rooms", level="Sailor", requires=["http_curl", "plato_submit"], estimated_xp=500, quests=["Map 5 rooms", "Find a hidden room"])
        cv.add_competency("repo_audit", "Audit GitHub repos", level="Sailor", requires=["http_curl"], estimated_xp=400, quests=["Fix dead links", "Add .gitignore"])
        cv.add_competency("subagent_spawn", "Spawn and monitor subagents", level="Officer", requires=["repo_audit", "mud_explore"], estimated_xp=800, quests=["Spawn 3 subagents", "Harvest their results"])
        cv.add_competency("bottle_write", "Write fleet bottles", level="Officer", requires=["plato_submit", "repo_audit"], estimated_xp=600, quests=["Drop bottle to Oracle1"])
        cv.add_competency("service_heal", "Fix downed services", level="Captain", requires=["subagent_spawn", "bottle_write"], estimated_xp=1200, quests=["Restart a service", "Patch a bug"])
        cv.add_competency("fleet_orchestrate", "Orchestrate fleet-wide operations", level="Admiral", requires=["service_heal"], estimated_xp=2000, quests=["Coordinate 10+ agents", "Design new curriculum"])
        return cv


if __name__ == "__main__":
    cv = Curriculum.fleet_default()
    print("=== Fleet Curriculum ===")
    print(f"Competencies: {len(cv.competencies)}")
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
        print(f"  - {c.name} ({c.id})")
    print()
    print(f"Next quests: {cv.next_quests(shell)}")
    print()
    print(f"Path to 'fleet_orchestrate':")
    for c in cv.learning_path("fleet_orchestrate"):
        print(f"  → {c.name}")
    print()
    print(f"Level progress: {cv.level_progress(shell)}")
    print()
    cv.save("fleet_curriculum.json")
    print("Saved to fleet_curriculum.json")
