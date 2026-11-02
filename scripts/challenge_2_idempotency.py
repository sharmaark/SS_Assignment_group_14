import os
from pathlib import Path
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    environment = os.environ.copy()
    environment.setdefault(
        "DISPATCH_DATABASE_URL",
        "sqlite:///dispatch-import.db",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-c",
            "services/dispatch/pytest.ini",
            "services/dispatch/tests/test_api.py",
            "-k",
            "simultaneous_duplicates_execute_one_flow",
            "-s",
        ],
        cwd=REPO_ROOT,
        env=environment,
        check=False,
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())