"""Serve only the compiled public frontend, sharing the API's origin."""

from pathlib import Path

from starlette.staticfiles import StaticFiles


class FrontendFiles(StaticFiles):
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = (
            "public, max-age=31536000, immutable" if path.startswith("assets/") else "no-cache")
        return response


def mount_frontend(app):
    directory = Path(__file__).resolve().parents[1] / "Frontend" / "dist"
    if (directory / "index.html").is_file():
        app.mount("/", FrontendFiles(directory=directory, html=True), name="frontend")
