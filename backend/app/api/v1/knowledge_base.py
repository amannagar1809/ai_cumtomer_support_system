"""Knowledge base API endpoints."""

import base64
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.knowledge_base import (
    DeleteDocumentRequest,
    DeleteDocumentResponse,
    SupportedFileTypesResponse,
    UploadDocumentRequest,
    UploadDocumentResponse,
)
from app.services.knowledge_base.document_processor import (
    DocumentProcessor,
    SUPPORTED_FILE_TYPES,
)
from app.services.knowledge_base.vector_store import VectorStore, VectorDBProvider

router = APIRouter(prefix="/knowledge-base", tags=["knowledge-base"])


@router.post(
    "/upload",
    response_model=UploadDocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Upload document to knowledge base (admin only)",
)
async def upload_document(
    body: UploadDocumentRequest,
    db: AsyncSession = Depends(get_db),
) -> UploadDocumentResponse:
    """
    Upload a document to the knowledge base.

    This endpoint:
    - Accepts document file (PDF, DOCX, TXT, Markdown, HTML)
    - Extracts text from document
    - Cleans and chunks the text
    - Generates embeddings for chunks
    - Stores chunks in vector database

    Args:
        body: Upload request with file data
        db: Database session

    Returns:
        Upload response with document metadata
    """
    # TODO: Add admin-only authentication check
    # For now, this endpoint is open but should be restricted to admins

    try:
        # Validate file type
        if body.file_type.lower() not in SUPPORTED_FILE_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type. Supported types: {', '.join(SUPPORTED_FILE_TYPES)}",
            )

        # Decode base64 file data
        file_data = base64.b64decode(body.file_data)

        # Initialize document processor
        processor = DocumentProcessor()

        # Process document
        chunks, metadata = processor.process_document(
            file_data=file_data,
            filename=body.filename,
            file_type=body.file_type.lower(),
        )

        # Initialize vector store
        vector_store = VectorStore(provider=VectorDBProvider.pgvector)

        # Convert chunks to dict format for storage
        chunks_to_store = [
            {
                "chunk_id": chunk.chunk_id,
                "document_id": chunk.document_id,
                "text": chunk.text,
                "embedding": chunk.embedding,
                "chunk_index": chunk.chunk_index,
                "start_char": chunk.start_char,
                "end_char": chunk.end_char,
            }
            for chunk in chunks
        ]

        # Store chunks in vector database
        store_result = vector_store.store_chunks(chunks_to_store)

        if not store_result.success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to store chunks in vector database: {store_result.message}",
            )

        return UploadDocumentResponse(
            document_id=metadata.document_id,
            filename=metadata.filename,
            file_type=metadata.file_type,
            file_size=metadata.file_size,
            text_length=metadata.text_length,
            chunk_count=metadata.chunk_count,
            processing_time_ms=metadata.processing_time_ms,
            success=True,
            message=f"Document uploaded successfully. Created {metadata.chunk_count} chunks.",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Document upload failed: {str(e)}",
        )


@router.delete(
    "/document",
    response_model=DeleteDocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete document from knowledge base (admin only)",
)
async def delete_document(
    body: DeleteDocumentRequest,
    db: AsyncSession = Depends(get_db),
) -> DeleteDocumentResponse:
    """
    Delete a document from the knowledge base.

    Args:
        body: Delete request with document ID
        db: Database session

    Returns:
        Delete response
    """
    # TODO: Add admin-only authentication check

    try:
        # Initialize vector store
        vector_store = VectorStore(provider=VectorDBProvider.pgvector)

        # Delete document chunks
        delete_result = vector_store.delete_document(body.document_id)

        if not delete_result.success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete document: {delete_result.message}",
            )

        return DeleteDocumentResponse(
            document_id=body.document_id,
            success=True,
            message="Document deleted successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Document deletion failed: {str(e)}",
        )


@router.get(
    "/file-types",
    response_model=SupportedFileTypesResponse,
    status_code=status.HTTP_200_OK,
    summary="Get supported file types",
)
async def get_supported_file_types(
    db: AsyncSession = Depends(get_db),
) -> SupportedFileTypesResponse:
    """
    Get list of supported file types for document upload.

    Args:
        db: Database session

    Returns:
        Supported file types
    """
    return SupportedFileTypesResponse(file_types=SUPPORTED_FILE_TYPES)
