import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from servidor_central.database import init_db
from servidor_central.routes import router


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


def get_frontend_dist_path() -> Path:
    configured_path = os.getenv("FRONTEND_DIST_PATH")
    if configured_path:
        return Path(configured_path)

    return Path(__file__).resolve().parent.parent / "front" / "dist"


def _resolve_frontend_file(requested_path: str) -> Path | None:
    dist_path = get_frontend_dist_path().resolve()
    candidate = (dist_path / requested_path).resolve()

    try:
        candidate.relative_to(dist_path)
    except ValueError:
        return None

    return candidate


def create_app() -> FastAPI:
    app = FastAPI(
        title="Smart Cart API",
        description="Servidor central do prototipo Smart Cart.",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.include_router(router)

    @app.get("/app", include_in_schema=False)
    @app.get("/app/{full_path:path}", include_in_schema=False)
    def serve_frontend(full_path: str = "") -> FileResponse:
        dist_path = get_frontend_dist_path()
        index_path = dist_path / "index.html"

        if not index_path.exists():
            raise HTTPException(
                status_code=404,
                detail="Build do frontend nao encontrado. Execute o build em front/ antes de servir /app.",
            )

        if full_path:
            requested_file = _resolve_frontend_file(full_path)
            if requested_file and requested_file.is_file():
                return FileResponse(requested_file)

            if "." in Path(full_path).name:
                raise HTTPException(status_code=404, detail="Asset do frontend nao encontrado.")

        return FileResponse(index_path)

    return app


app = create_app()
