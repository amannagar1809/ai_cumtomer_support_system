"""OAuth2 API endpoints."""

from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.core.jwt import ACCESS_TOKEN_EXPIRE_MINUTES
from app.core.oauth import oauth_service
from app.core.database import get_db
from app.schemas.oauth import (
    LinkedAccountsResponse,
    LinkOAuthAccountRequest,
    LinkOAuthAccountResponse,
    OAuthAccountInfo,
    OAuthLoginResponse,
    UnlinkOAuthAccountResponse,
)
from app.services.auth.oauth_service import OAuth2Service

router = APIRouter(prefix="/oauth", tags=["oauth"])


@router.get(
    "/login/{provider}",
    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    summary="Initiate OAuth login"
)
async def oauth_login(provider: str, request: Request):
    """
    Initiate OAuth login flow.

    This endpoint:
    - Redirects to OAuth provider authorization page
    - Supports: google, microsoft, github, slack

    Args:
        provider: OAuth provider (google, microsoft, github, slack)
        request: FastAPI request

    Returns:
        Redirect to OAuth provider
    """
    # Check if provider is enabled
    if not oauth_service.is_provider_enabled(provider):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth provider '{provider}' is not enabled",
        )

    # Get OAuth client
    client = oauth_service.get_client(provider)

    if not client:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create OAuth client for provider '{provider}'",
        )

    # Build redirect URI
    redirect_uri = str(request.url_for("oauth_callback", provider=provider))

    # Redirect to OAuth provider
    return await client.authorize_redirect(request, redirect_uri)


@router.get(
    "/callback/{provider}",
    response_model=OAuthLoginResponse,
    status_code=status.HTTP_200_OK,
    summary="OAuth callback"
)
async def oauth_callback(
    provider: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> OAuthLoginResponse:
    """
    Handle OAuth callback.

    This endpoint:
    - Exchanges authorization code for tokens
    - Fetches user info from provider
    - Creates or links user account
    - Issues JWT tokens

    Args:
        provider: OAuth provider
        request: FastAPI request
        db: Database session

    Returns:
        OAuth login response with tokens
    """
    # Check if provider is enabled
    if not oauth_service.is_provider_enabled(provider):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth provider '{provider}' is not enabled",
        )

    # Get OAuth client
    client = oauth_service.get_client(provider)

    if not client:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create OAuth client for provider '{provider}'",
        )

    # Build redirect URI
    redirect_uri = str(request.url_for("oauth_callback", provider=provider))

    try:
        # Exchange authorization code for token
        token = await client.authorize_access_token(request, redirect_uri=redirect_uri)

        # Parse token
        access_token = token.get("access_token")
        refresh_token = token.get("refresh_token")
        expires_in = token.get("expires_in")
        token_expires_at = None

        if expires_in:
            token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

        # Fetch user info
        user_info = await client.parse_id_token(request, token) if provider in ["google", "microsoft"] else await client.userinfo(token=token)

        # Get client info
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")

        # Initialize OAuth service
        oauth2_service = OAuth2Service(db)

        # Handle OAuth callback
        result = await oauth2_service.handle_oauth_callback(
            provider=provider,
            user_info=user_info,
            access_token=access_token,
            refresh_token=refresh_token,
            token_expires_at=token_expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        if not result:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to process OAuth callback",
            )

        user, jwt_access_token, jwt_refresh_token = result

        return OAuthLoginResponse(
            access_token=jwt_access_token,
            refresh_token=jwt_refresh_token,
            token_type="bearer",
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user_id=user.id,
            email=user.email,
            name=user.name,
            role=user.role,
            provider=provider,
            is_new_user=user.auth_provider == provider and user.created_at >= datetime.utcnow() - timedelta(minutes=5),
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OAuth callback error: {str(e)}",
        )


@router.get(
    "/accounts",
    response_model=LinkedAccountsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get linked OAuth accounts"
)
async def get_linked_accounts(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LinkedAccountsResponse:
    """
    Get all OAuth accounts linked to current user.

    Args:
        current_user: Current user from JWT
        db: Database session

    Returns:
        List of linked OAuth accounts
    """
    user_id = UUID(current_user["sub"])

    # Initialize OAuth service
    oauth2_service = OAuth2Service(db)

    # Get OAuth accounts
    oauth_accounts = await oauth2_service.get_user_oauth_accounts(user_id)

    # Convert to response format
    account_infos = [
        OAuthAccountInfo(
            id=account.id,
            provider=account.provider,
            email=account.email,
            name=account.name,
            avatar_url=account.avatar_url,
            created_at=account.created_at.isoformat(),
        )
        for account in oauth_accounts
    ]

    return LinkedAccountsResponse(
        user_id=user_id,
        oauth_accounts=account_infos,
    )


@router.post(
    "/link",
    response_model=LinkOAuthAccountResponse,
    status_code=status.HTTP_200_OK,
    summary="Link OAuth account"
)
async def link_oauth_account(
    body: LinkOAuthAccountRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LinkOAuthAccountResponse:
    """
    Link OAuth account to current user.

    Args:
        body: Link request with provider and authorization code
        request: FastAPI request
        current_user: Current user from JWT
        db: Database session

    Returns:
        Link response
    """
    provider = body.provider

    # Check if provider is enabled
    if not oauth_service.is_provider_enabled(provider):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth provider '{provider}' is not enabled",
        )

    # Get OAuth client
    client = oauth_service.get_client(provider)

    if not client:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create OAuth client for provider '{provider}'",
        )

    # Build redirect URI
    redirect_uri = str(request.url_for("oauth_link_callback", provider=provider))

    try:
        # Exchange authorization code for token
        token = await client.authorize_access_token(request, redirect_uri=redirect_uri, code=body.authorization_code)

        # Parse token
        access_token = token.get("access_token")
        refresh_token = token.get("refresh_token")
        expires_in = token.get("expires_in")
        token_expires_at = None

        if expires_in:
            token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

        # Fetch user info
        user_info = await client.parse_id_token(request, token) if provider in ["google", "microsoft"] else await client.userinfo(token=token)

        # Initialize OAuth service
        oauth2_service = OAuth2Service(db)
        user_id = UUID(current_user["sub"])

        # Link OAuth account
        success = await oauth2_service.link_oauth_account(
            user_id=user_id,
            provider=provider,
            user_info=user_info,
            access_token=access_token,
            refresh_token=refresh_token,
            token_expires_at=token_expires_at,
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to link OAuth account",
            )

        # Get updated OAuth accounts
        oauth_accounts = await oauth2_service.get_user_oauth_accounts(user_id)
        linked_account = next(
            (acc for acc in oauth_accounts if acc.provider == provider),
            None,
        )

        account_info = None
        if linked_account:
            account_info = OAuthAccountInfo(
                id=linked_account.id,
                provider=linked_account.provider,
                email=linked_account.email,
                name=linked_account.name,
                avatar_url=linked_account.avatar_url,
                created_at=linked_account.created_at.isoformat(),
            )

        return LinkOAuthAccountResponse(
            success=True,
            message="OAuth account linked successfully",
            account=account_info,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OAuth link error: {str(e)}",
        )


@router.delete(
    "/unlink/{provider}",
    response_model=UnlinkOAuthAccountResponse,
    status_code=status.HTTP_200_OK,
    summary="Unlink OAuth account"
)
async def unlink_oauth_account(
    provider: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UnlinkOAuthAccountResponse:
    """
    Unlink OAuth account from current user.

    Args:
        provider: OAuth provider to unlink
        current_user: Current user from JWT
        db: Database session

    Returns:
        Unlink response
    """
    user_id = UUID(current_user["sub"])

    # Initialize OAuth service
    oauth2_service = OAuth2Service(db)

    # Unlink OAuth account
    success = await oauth2_service.unlink_oauth_account(user_id, provider)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to unlink OAuth account for provider '{provider}'",
        )

    return UnlinkOAuthAccountResponse(
        success=True,
        message=f"OAuth account for provider '{provider}' unlinked successfully",
    )
