from fastapi import FastAPI, HTTPException
from sqlalchemy.exc import SQLAlchemyError

from app.database.session import check_database_connection

app = FastAPI(
    title="Production Event Processing API",
    version="1.0.0",
)


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
