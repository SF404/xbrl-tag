from datetime import timedelta
import jwt
import requests
from fastapi import APIRouter, HTTPException

from app.core.config import get_config
from app.core.security import create_access_token
from app.schemas.schemas import LoginRequest, Token

router = APIRouter(prefix="/token")
config = get_config()


@router.post("/generate", response_model=Token)
def generate_token(login_data: LoginRequest):
    """
    Authenticates against an external service and generates a local JWT.
    """
    # Step 1: Authenticate with the external service
    try:
        payload = {"email": login_data.email, "password": login_data.password}
        response = requests.post(
            config.AUTH_BACKEND_ENDPOINT, json=payload
        )

        print(response)
        response.raise_for_status()
        user_data = response.json()

    except requests.exceptions.HTTPError as e:
        # Proxy HTTP errors from the auth service (e.g., 401, 404)
        raise HTTPException(
            status_code=e.response.status_code,
            detail={
                "msg": "Invalid Credentials: Authentication failed with the external service.",
                "upstream_detail": e.response.text,
            },
        ) from e

    except requests.exceptions.RequestException as e:
        # Handle network-related errors (e.g., connection refused, timeout)
        raise HTTPException(
            status_code=503,
            detail="External authentication service is unavailable.",
        ) from e


    # Step 2: Determine access level based on user role from the external service

    user = user_data.get("user") or {}
    if not user:
        raise HTTPException(status_code=502, detail="Upstream did not return user data")
    
    user_role = user.get("role")
    print(user_role)

    if user_role == "user":
        access_level = 1
    elif user_role == "admin":
        access_level = 7
    else:
        access_level = 0

    # Step 3: Create a local access token with the determined access level
    # Note: token expiration is currently disabled (set to None).
    # To enable, uncomment the following line:
    # access_token_expires = timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token_expires = None

    access_token = create_access_token(
        data={"sub": login_data.email, "access_level": access_level},
        expires_delta=access_token_expires,
    )

    return {"access_token": access_token, "token_type": "bearer"}