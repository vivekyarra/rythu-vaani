import os
import sys
from pathlib import Path

# Force MOCK mode for the whole test run, even if a real key sits in .env:
# load_dotenv(override=False) leaves an already-set (empty) variable alone.
os.environ["GNANI_API_KEY"] = ""
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
