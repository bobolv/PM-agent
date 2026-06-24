from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session

from pm_agent.api.routes import router
from pm_agent.config import get_settings
from pm_agent.db import engine, init_db
from pm_agent.logging import configure_logging
from pm_agent.services import CatalogService
from pm_agent.template_library import TemplateLibraryService


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="PM Agent API",
        description="项目生命周期文档生成与管理 API",
        version="0.1.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    def on_startup() -> None:
        init_db()
        with Session(engine) as session:
            CatalogService(session).seed_document_catalog()
            TemplateLibraryService(session, settings).generate_missing_templates()

    app.include_router(router)

    frontend_dir = Path(__file__).resolve().parents[3] / "frontend"
    index_file = frontend_dir / "index.html"
    if index_file.exists():
        app.mount("/static", StaticFiles(directory=frontend_dir), name="frontend-static")

        @app.get("/", include_in_schema=False)
        def frontend_index() -> FileResponse:
            return FileResponse(index_file)

    return app


app = create_app()


def run() -> None:
    uvicorn.run("pm_agent.api.main:app", host="0.0.0.0", port=8000, reload=True)
