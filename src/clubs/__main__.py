import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]

import uvicorn  # noqa: E402

# Get arguments from command
args = sys.argv[1:]
extended_args = [
    "src.clubs.app:app",
    "--use-colors",
    "--proxy-headers",
    "--forwarded-allow-ips=*",
    "--port=8014",
    *args,
]

print(f"🚀 Starting Uvicorn server: 'uvicorn {' '.join(extended_args)}'")
uvicorn.main.main(extended_args)
