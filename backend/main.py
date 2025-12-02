from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from config.setting import settings
from routes.document import router as documents_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents_router)


# ==================== РАЗДАЧА HTML ФРОНТЕНДА ====================

@app.get("/")
async def serve_frontend():
    """Раздаём HTML фронтенд"""
    frontend_path = Path(__file__).parent / "test.html"
    return FileResponse(frontend_path)


@app.get("/health", tags=["info"])
async def health_check():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.HOST,
        port=settings.PORT
    )
