import os
import sys
import tempfile
from pathlib import Path

_tmp = Path(tempfile.mkdtemp(prefix="evidra-test-"))
os.environ["EVIDRA_ENV"] = "test"
os.environ["EVIDRA_DATABASE_URL"] = f"sqlite:///{_tmp / 'test.db'}"
os.environ["EVIDRA_STORAGE_DIR"] = str(_tmp / "storage")
os.environ["EVIDRA_AI_ENGINE"] = "heuristic"
os.environ["EVIDRA_AUTO_SEED"] = "false"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402


@pytest.fixture(scope="session")
def tmp_root() -> Path:
    return _tmp
