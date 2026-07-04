"""Authentication API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_current_user, get_optional_user
from app.core.jwt import ACCESS_TOKEN_EXPIRE_MINUTES
from app.core.database import get_db
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    LogoutResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
    TokenValidationResponse,
)
from app.services.auth.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="User login"
)
async def login(
    body: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """
    Authenticate user and return JWT tokens.

    This endpoint:
    - Validates user credentials
    - Issues access token (15 min expiry)
    - Issues refresh token (7 day expiry)
    - Stores refresh token in Redis
    - Logs authentication attempt

    Args:
        body: Login request with email and password
        request: FastAPI request for IP and user agent
        db: Database session

    Returns:
        Login response with tokens and user info
    """
    # Get client info
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    # Initialize auth service
    auth_service = AuthService(db)

    # Authenticate user
    result = await auth_service.authenticate_user(
        email=body.email,
        password=body.password,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user, access_token, refresh_token = result

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user_id=user.id,
        email=user.email,
        role=user.role,
    )


@router.post(
    "/refresh",
    response_model=RefreshTokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh access token"
)
async def refresh_token(
    body: RefreshTokenRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> RefreshTokenResponse:
    """
    Refresh access token using refresh token.

    This endpoint:
    - Validates refresh token
    - Checks against stored token in Redis
    - Issues new access and refresh tokens
    - Logs refresh attempt

    Args:
        body: Refresh token request
        request: FastAPI request for IP and user agent
        db: Database session

    Returns:
        Refresh response with new tokens
    """
    # Get client info
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    # Initialize auth service
    auth_service = AuthService(db)

    # Refresh tokens
    result = await auth_service.refresh_tokens(
        refresh_token=body.refresh_token,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    new_access_token, new_refresh_token = result

    return RefreshTokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post(
    "/logout",
    response_model=LogoutResponse,
    status_code=status.HTTP_200_OK,
    summary="User logout"
)
async def logout(
    body: LogoutRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> LogoutResponse:
    """
    Logout user by blacklisting tokens.

    This endpoint:
    - Blacklists access token
    - Deletes refresh token from Redis
    - Logs logout attempt

    Args:
        body: Logout request with optional refresh token
        request: FastAPI request for IP and user agent
        db: Database session

    Returns:
        Logout response
    """
    # Get client info
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    # Get access token from authorization header
    auth_header = request.headers.get("authorization")
    access_token = None
    if auth_header and auth_header.startswith("Bearer "):
        access_token = auth_header[7:]

    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Access token required",
        )

    # Initialize auth service
    auth_service = AuthService(db)

    # Logout user
    success = await auth_service.logout(
        access_token=access_token,
        refresh_token=body.refresh_token,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Logout failed",
        )

    return LogoutResponse(
        success=True,
        message="Logged out successfully",
    )


@router.get(
    "/validate",
    response_model=TokenValidationResponse,
    status_code=status.HTTP_200_OK,
    summary="Validate access token"
)
async def validate_token(
    current_user: dict = Depends(get_optional_user),
) -> TokenValidationResponse:
    """
    Validate access token.

    This endpoint:
    - Validates JWT token
    - Returns user info if valid

    Args:
        current_user: Current user from token (optional)

    Returns:
        Token validation response
    """
    if not current_user:
        return TokenValidationResponse(
            valid=False,
            user_id=None,
            email=None,
            role=None,
        )

    return TokenValidationResponse(
        valid=True,
        user_id=current_user.get("sub"),
        email=current_user.get("email"),
        role=current_user.get("role"),
    )
