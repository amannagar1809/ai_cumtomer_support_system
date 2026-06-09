from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse, Response

from app.core.config import settings
from app.schemas.upload import (
    CompleteUploadRequest,
    CompleteUploadResponse,
    InitUploadRequest,
    InitUploadResponse,
    UploadLimitsResponse,
)
from app.services.file_upload import FileUploadError, FileUploadService
from app.services.storage.local import LocalStorageBackend
from app.services.storage.factory import get_storage_backend

router = APIRouter(prefix="/chat/uploads", tags=["uploads"])


@router.get("/limits", response_model=UploadLimitsResponse)
def get_upload_limits() -> UploadLimitsResponse:
    return FileUploadService().limits()


@router.post("/init", response_model=InitUploadResponse)
async def init_upload(body: InitUploadRequest) -> InitUploadResponse:
    service = FileUploadService()
    try:
        return await service.init_upload(body)
    except FileUploadError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.put("/{upload_id}/chunks/{chunk_index}")
async def upload_chunk(
    upload_id: UUID,
    chunk_index: int,
    request: Request,
    anonymous_user_id: UUID,
) -> dict[str, str]:
    """Local storage backend: receive chunked upload data."""
    if settings.storage_provider.lower() != "local":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Direct chunk upload is only used for local storage. Upload to pre-signed URLs.",
        )
    data = await request.body()
    service = FileUploadService()
    try:
        await service.store_chunk(
            upload_id,
            chunk_index,
            data,
            anonymous_user_id=anonymous_user_id,
        )
    except FileUploadError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"status": "ok"}


@router.post("/{upload_id}/complete", response_model=CompleteUploadResponse)
async def complete_upload(
    upload_id: UUID,
    body: CompleteUploadRequest,
) -> CompleteUploadResponse:
    if body.upload_id != upload_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Upload ID mismatch")
    service = FileUploadService()
    try:
        return await service.complete_upload(
            upload_id,
            anonymous_user_id=body.anonymous_user_id,
            conversation_id=body.conversation_id,
        )
    except FileUploadError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/files/{file_id}")
async def serve_uploaded_file(
    file_id: UUID,
    expires: int,
    token: str,
):
    """Serve local uploads via HMAC-signed URL."""
    if settings.storage_provider.lower() != "local":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    backend = get_storage_backend()
    if not isinstance(backend, LocalStorageBackend):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    if not backend.verify_signed_url(file_id, expires, token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid or expired URL")

    from pathlib import Path

    path = Path(settings.upload_local_dir) / "files" / str(file_id)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    return FileResponse(path)
