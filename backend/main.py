"""
UB Time Bomb Detector — FastAPI application entry point.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import CORS_ORIGINS
from models.database import init_db
from routers.analysis import router as analysis_router
from routers.scans import router as scans_router
from routers.evaluation import router as eval_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="UB Time Bomb Detector API",
    description=(
        "Static analysis tool that detects C/C++ undefined behavior patterns "
        "that are benign at -O0 but exploited by compiler optimizations at -O2/-O3."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS + ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analysis_router)
app.include_router(scans_router)
app.include_router(eval_router)


@app.get("/api/v1/health")
async def health():
    import subprocess
    try:
        r = subprocess.run(["clang", "--version"], capture_output=True, timeout=3)
        clang_ver = r.stdout.decode().split("\n")[0] if r.returncode == 0 else "unavailable"
    except Exception:
        clang_ver = "unavailable"
    return {"status": "ok", "version": "1.0.0", "clang": clang_ver}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
