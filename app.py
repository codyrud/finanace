import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP_DIR = ROOT / "option-pricer"

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from streamlit_app import app


if __name__ == "__main__":
    app()
