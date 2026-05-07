import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]

os.chdir(BASE_DIR)

import uvicorn  # noqa: E402

# Get arguments from command
args = sys.argv[1:]
extended_args = [
    "src.student_affairs.app:app",
    "--use-colors",
    "--proxy-headers",
    "--forwarded-allow-ips=*",
    "--port=8015",
    *args,
]

print(f"🚀 Starting Uvicorn server: 'uvicorn {' '.join(extended_args)}'")
uvicorn.main.main(extended_args)
