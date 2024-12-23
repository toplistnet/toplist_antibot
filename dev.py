"""
Runs the application for local development. This file should not be used to start the
application for production.

Refer to https://www.uvicorn.org/deployment/ for production deployments.
"""
import sys
sys.dont_write_bytecode = True

import os

import uvicorn
from rich.console import Console

try:
    import uvloop
except ModuleNotFoundError:
    pass
else:
    uvloop.install()

if __name__ == "__main__":
    os.environ["APP_ENV"] = "dev"
    port: int = 8099

    console = Console()
    console.print(f"[bold yellow]Visit http://localhost:{port}/")

    uvicorn.run(
        app="app.app:app",
        host='0.0.0.0',
        port=port,
        lifespan="on",
        log_level="info",
        reload=True,
        proxy_headers=True,
        forwarded_allow_ips='*',
        # log_config='logging.conf',
        reload_includes=["*.py", "*.css", "*.js", "*.html", "*.yaml", '*.cfg'],
    )
