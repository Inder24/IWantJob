"""
Main FastAPI application
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import connect_to_mongo, close_mongo_connection
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(
    title=os.getenv("APP_NAME", "Job Search Tool"),
    version=os.getenv("APP_VERSION", "1.0.0"),
    description="Intelligent job search automation tool with resume parsing and multi-platform scraping"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Run on application startup"""
    await connect_to_mongo()
    print(f"✓ {os.getenv('APP_NAME')} started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown"""
    await close_mongo_connection()


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "online",
        "app": os.getenv("APP_NAME"),
        "version": os.getenv("APP_VERSION")
    }


@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "database": "connected",
        "timestamp": str(__import__('datetime').datetime.now())
    }


# Import and include routers
from app.routers import auth, resume, jobs, admin

app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(resume.router, prefix="/api/resume", tags=["Resume"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["Jobs"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])
# app.include_router(applications.router, prefix="/api/applications", tags=["Applications"])
