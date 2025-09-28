from typing import Callable, Generator

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.managers.jobs_manager import JobsManager
from app.schemas.schemas import TokenData
from app.services import ModelRegistry, VectorstoreService


def get_db() -> Generator[Session, None, None]:
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


async def get_current_user(request: Request) -> TokenData:
    user = request.state.user
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_access_level(required_level: int) -> Callable:
    def dependency(current_user: TokenData = Depends(get_current_user)) -> TokenData:
        if (
            current_user.access_level is None
            or current_user.access_level < required_level
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have sufficient access rights.",
            )
        return current_user

    return dependency
