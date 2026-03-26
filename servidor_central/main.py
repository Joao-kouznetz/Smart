from contextlib import asynccontextmanager

from fastapi import FastAPI

from servidor_central.database import init_db
from servidor_central.routes import router


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Smart Cart API",
        description="Servidor central do prototipo Smart Cart.",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.include_router(router)
    return app


app = create_app()
