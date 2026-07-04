"""Knowledge base API endpoints."""

import base64
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.knowledge_base import (
    DeleteDocumentRequest,
    DeleteDocumentResponse,
    KnowledgeCategoriesResponse,
    ReplaceDocumentVersionRequest,
    ReplaceDocumentVersionResponse,
    ReviewDocumentRequest,
    ReviewDocumentResponse,
    SupportedFileTypesResponse,
    UploadDocumentRequest,
    UploadDocumentResponse,
)
from app.services.knowledge_base.document_processor import (
    DocumentProcessor,
    KNOWLEDGE_CATEGORIES,
    REVIEW_STATUS_APPROVED,
    REVIEW_STATUS_PENDING,
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
    - Stores chunks in vector database with metadata
    - Sets review status to pending

    Args:
        body: Upload request with file data, category, and version
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

        # Validate category
        if body.category.lower() not in KNOWLEDGE_CATEGORIES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid category. Supported categories: {', '.join(KNOWLEDGE_CATEGORIES)}",
            )

        # Decode base64 file data
        file_data = base64.b64decode(body.file_data)

        # Initialize document processor
        processor = DocumentProcessor()

        # Process document with category and version
        chunks, metadata = processor.process_document(
            file_data=file_data,
            filename=body.filename,
            file_type=body.file_type.lower(),
            category=body.category.lower(),
            version=body.version,
        )

        # Initialize vector store
        vector_store = VectorStore(provider=VectorDBProvider.pgvector)

        # Convert chunks to dict format for storage with metadata
        chunks_to_store = [
            {
                "chunk_id": chunk.chunk_id,
                "document_id": chunk.document_id,
                "text": chunk.text,
                "embedding": chunk.embedding,
                "chunk_index": chunk.chunk_index,
                "start_char": chunk.start_char,
                "end_char": chunk.end_char,
                "source_document": chunk.source_document,
                "category": chunk.category,
                "version": chunk.version,
                "last_updated": chunk.last_updated.isoformat(),
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
            category=metadata.category,
            version=metadata.version,
            review_status=metadata.review_status,
            uploaded_at=metadata.uploaded_at,
            success=True,
            message=f"Document uploaded successfully. Created {metadata.chunk_count} chunks. Review status: pending.",
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


@router.post(
    "/replace-version",
    response_model=ReplaceDocumentVersionResponse,
    status_code=status.HTTP_200_OK,
    summary="Replace document version (admin only)",
)
async def replace_document_version(
    body: ReplaceDocumentVersionRequest,
    db: AsyncSession = Depends(get_db),
) -> ReplaceDocumentVersionResponse:
    """
    Replace an old document version with a new version.

    This endpoint:
    - Deletes old document chunks
    - Processes and stores new document chunks
    - Updates version metadata

    Args:
        body: Replace version request
        db: Database session

    Returns:
        Replacement response
    """
    # TODO: Add admin-only authentication check

    try:
        # Validate file type
        if body.file_type.lower() not in SUPPORTED_FILE_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type. Supported types: {', '.join(SUPPORTED_FILE_TYPES)}",
            )

        # Validate category
        if body.category.lower() not in KNOWLEDGE_CATEGORIES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid category. Supported categories: {', '.join(KNOWLEDGE_CATEGORIES)}",
            )

        # Decode base64 file data
        file_data = base64.b64decode(body.file_data)

        # Initialize document processor
        processor = DocumentProcessor()

        # Process new document
        chunks, metadata = processor.process_document(
            file_data=file_data,
            filename=body.filename,
            file_type=body.file_type.lower(),
            category=body.category.lower(),
            version=body.version,
            document_id=body.old_document_id,  # Use same document ID for versioning
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
                "source_document": chunk.source_document,
                "category": chunk.category,
                "version": chunk.version,
                "last_updated": chunk.last_updated.isoformat(),
            }
            for chunk in chunks
        ]

        # Replace old version with new version
        replace_result = vector_store.replace_document_version(
            old_document_id=body.old_document_id,
            new_chunks=chunks_to_store,
        )

        if not replace_result.success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to replace document version: {replace_result.message}",
            )

        return ReplaceDocumentVersionResponse(
            old_document_id=body.old_document_id,
            new_document_id=metadata.document_id,
            success=True,
            message=f"Document version replaced successfully. New version: {body.version}",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Document version replacement failed: {str(e)}",
        )


@router.post(
    "/review",
    response_model=ReviewDocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Review document (admin only)",
)
async def review_document(
    body: ReviewDocumentRequest,
    db: AsyncSession = Depends(get_db),
) -> ReviewDocumentResponse:
    """
    Review a document and approve or reject it.

    This endpoint:
    - Updates document review status
    - Stores review notes if provided
    - Approved documents become available for retrieval

    Args:
        body: Review request with document ID and status
        db: Database session

    Returns:
        Review response
    """
    # TODO: Add admin-only authentication check

    try:
        # Validate review status
        if body.review_status.lower() not in [REVIEW_STATUS_APPROVED, "rejected"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid review status. Must be 'approved' or 'rejected'",
            )

        # Initialize vector store
        vector_store = VectorStore(provider=VectorDBProvider.pgvector)

        # Update chunk metadata with review status
        # In production, this would update all chunks for the document
        metadata_update = {
            "review_status": body.review_status.lower(),
            "review_notes": body.review_notes,
        }

        # Placeholder: Update metadata for document chunks
        # In production, this would query all chunks for the document and update them
        success = vector_store.update_chunk_metadata(
            chunk_id=f"{body.document_id}_chunk_0",  # Placeholder chunk ID
            metadata=metadata_update,
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update document review status",
            )

        return ReviewDocumentResponse(
            document_id=body.document_id,
            review_status=body.review_status.lower(),
            review_notes=body.review_notes,
            success=True,
            message=f"Document review status updated to {body.review_status.lower()}",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Document review failed: {str(e)}",
        )


@router.get(
    "/categories",
    response_model=KnowledgeCategoriesResponse,
    status_code=status.HTTP_200_OK,
    summary="Get knowledge categories",
)
async def get_knowledge_categories(
    db: AsyncSession = Depends(get_db),
) -> KnowledgeCategoriesResponse:
    """
    Get list of knowledge categories.

    Args:
        db: Database session

    Returns:
        Knowledge categories
    """
    return KnowledgeCategoriesResponse(categories=KNOWLEDGE_CATEGORIES)
