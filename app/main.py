from contextlib import asynccontextmanager
from datetime import datetime
import logging

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text

from dotenv import load_dotenv

from app.api import services, incidents, dashboard
from app.api import projects, services_v2, incidents_v2, dashboard_v2
from app.api.v3 import projects as projects_v3, services as services_v3
from app.api.v3 import incidents as incidents_v3, dashboard as dashboard_v3
from app.api.v3 import user as user_v3
from app.core.database import get_db, engine, Base
from app.core.config import settings
from app.core.firebase import init_firebase
from app.scheduler import start_scheduler, stop_scheduler

import os

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

load_dotenv()  # ← 이게 핵심

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events"""
    # Startup
    logger.info("Starting ServiceSentinel Backend...")

    # Create database tables
    # Base.metadata.create_all(bind=engine)
    # DB 초기화 (테이블 전부 삭제)
    # Base.metadata.drop_all(bind=engine)
    # Base.metadata.create_all(bind=engine)

    logger.info("Database tables created/verified")

    # firebase initializing
    init_firebase()
    logger.info("Firebase initialized")

    # Start scheduler
    await start_scheduler()

    yield

    # Shutdown
    logger.info("Shutting down ServiceSentinel Backend...")
    await stop_scheduler()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-powered service monitoring with intelligent failure analysis",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers - V1 (Legacy, un-authenticated)
app.include_router(services.router, prefix="/api/v1")
app.include_router(incidents.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")

# Include routers - V2 (Project-scoped with authentication)
app.include_router(projects.router, prefix="/api/v2")
app.include_router(services_v2.router, prefix="/api/v2")
app.include_router(incidents_v2.router, prefix="/api/v2")
app.include_router(dashboard_v2.router, prefix="/api/v2")

# Include routers - V3 (Mandatory authentication with Firebase + Guest, strict project-scoping)
app.include_router(projects_v3.router, prefix="/api/v3")
app.include_router(services_v3.router, prefix="/api/v3")
app.include_router(incidents_v3.router, prefix="/api/v3")
app.include_router(dashboard_v3.router, prefix="/api/v3")
app.include_router(dashboard_v3.global_router, prefix="/api/v3")
app.include_router(user_v3.router, prefix="/api/v3")


@app.get("/")
def root():
    """Root endpoint"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "operational",
        "timestamp": datetime.utcnow()
    }


@app.get("/health")
def health_check():
    """Basic health check"""
    return {
        "status": "ok",
        "timestamp": datetime.utcnow()
    }


@app.get("/health/db")
def db_health(db: Session = Depends(get_db)):
    """Database health check"""
    try:
        db.execute(text("SELECT 1"))
        return {
            "status": "ok",
            "database": "connected",
            "timestamp": datetime.utcnow()
        }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "status": "error",
            "database": "disconnected",
            "error": str(e),
            "timestamp": datetime.utcnow()
        }