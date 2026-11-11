#!/usr/bin/env python3
"""
Compatibility entrypoint for deployments that start the proxy with
`python /app/ar_proxy.py`.

The application itself lives in proxy.py; this module only re-exports the ASGI
app and starts the server when the file is executed directly.
"""
import uvicorn

from proxy import HOST, PORT, TARGET, app

__all__ = ["app", "HOST", "PORT", "TARGET"]


if __name__ == "__main__":
    print(f"AgentRouter proxy  ->  {TARGET}")
    print(f"Listening on http://{HOST}:{PORT}")
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
