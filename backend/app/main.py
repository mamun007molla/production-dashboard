from fastapi import FastAPI, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from app.modules.state.router import router as state_router
from fastapi.middleware.cors import CORSMiddleware
from app.database.session import check_database_connection
from app.modules.events.router import router as events_router
from app.modules.acknowledgements.router import (
    router as acknowledgements_router,
)

app = FastAPI(
    title="Production Event Processing API",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(events_router)
app.include_router(state_router)
app.include_router(acknowledgements_router)
@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/health/database")
def database_health_check():
    try:
        check_database_connection()
        return {
            "status": "ok",
            "database": "connected",
        }
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="Database connection failed",
        )
