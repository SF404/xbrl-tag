from typing import Generator
from fastapi import Request
from app.db.session import SessionLocal
from app.services import ModelRegistry
from app.services import VectorstoreService
from app.managers.jobs_manager import JobsManager


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_registry(request: Request) -> ModelRegistry:
    return request.app.state.registry


def get_vectorstore_service(request: Request) -> VectorstoreService:
    return request.app.state.vectorstore_service


def get_jobs_manager(request: Request) -> JobsManager:
    return request.app.state.jobs_manager
