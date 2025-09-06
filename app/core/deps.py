from typing import Generator
from fastapi import Request
from app.db.session import SessionLocal
from app.services.model_registry_service import ModelRegistry


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_registry(request: Request) -> ModelRegistry:
    return request.app.state.registry
