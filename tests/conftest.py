"""
Configuration pytest partagée — ajoute src/ au sys.path pour que les tests
puissent importer les modules du projet (module_b.dax_fix_generator,
orchestrator.history_tracker, etc.) exactement comme app.py le fait.
"""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))