"""cocapn_curriculum — FLUX v3.0 Competency DAG.

Two API levels:

1. **Python-native** (`cocapn_curriculum`): Curriculum DAG with adaptive difficulty
2. **FLUX v3.0** (`cocapn_curriculum_flux`): Compiled bytecode modules with jump table,
   CAP_REQUIRE/CHECK_BOUNDS, personalized shell_bytecode()

Default import is FLUX v3.0 API.
"""
from cocapn_curriculum_flux import FluxCurriculum, Competency, Op, main as run_demo

try:
    from cocapn_curriculum import Curriculum
except ImportError:
    Curriculum = None

__version__ = "3.0.0"
__all__ = ["FluxCurriculum", "Competency", "Op", "run_demo"]
