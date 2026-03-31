"""Start script that reads PORT from environment."""
import os
import uvicorn

port = int(os.environ.get("PORT", "8000"))
uvicorn.run("hormuz_monitor.server:app", host="0.0.0.0", port=port)
