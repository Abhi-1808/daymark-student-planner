"""Shared production/QA policy and narrowly scoped API documentation assets."""

import base64
import hashlib
import json
from pathlib import Path
import re

from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html

SECURITY_HEADERS = json.loads((Path(__file__).resolve().parents[1] / "config" / "security-headers.json").read_text(encoding="utf-8"))
SWAGGER_ASSETS = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/"
REDOC_ASSETS = "https://cdn.jsdelivr.net/npm/redoc@2/bundles/"


def documentation_html(app, *, redoc=False):
    """Keep API docs working without enabling arbitrary inline app scripts."""
    if redoc:
        response = get_redoc_html(openapi_url=app.openapi_url, title=f"{app.title} - ReDoc",
                                  redoc_favicon_url="/icon.svg", with_google_fonts=False)
        assets = REDOC_ASSETS
    else:
        response = get_swagger_ui_html(openapi_url=app.openapi_url, title=f"{app.title} - Swagger UI",
                                       swagger_favicon_url="/icon.svg")
        assets = SWAGGER_ASSETS
    scripts = re.findall(r"<script\b[^>]*>(.*?)</script>", response.body.decode("utf-8"), re.DOTALL)
    hashes = ["'sha256-" + base64.b64encode(hashlib.sha256(script.encode()).digest()).decode() + "'"
              for script in scripts if script.strip()]
    policy = SECURITY_HEADERS["Content-Security-Policy"]
    policy = policy.replace("script-src 'self'", "script-src 'self' " + assets + " " + " ".join(hashes))
    policy = policy.replace("style-src 'self'", "style-src 'self' " + assets)
    response.headers["Content-Security-Policy"] = policy
    return response
