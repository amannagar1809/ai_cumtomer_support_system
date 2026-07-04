"""Knowledge base schemas."""

from datetime import datetime
from pydantic import BaseModel, Field


class UploadDocumentRequest(BaseModel):
    """Request to upload a document."""

    file_data: str = Field(..., description="Base64-encoded file data")
    filename: str = Field(..., description="Original filename")
    file_type: str = Field(..., description="File type (pdf, docx, txt, md, html)")
    category: str = Field(..., description="Knowledge category (products, policies, faqs, troubleshooting, processes)")
    version: str = Field(default="1.0", description="Document version")


class UploadDocumentResponse(BaseModel):
    """Response for document upload."""

    document_id: str = Field(..., description="Document ID")
    filename: str = Field(..., description="Original filename")
    file_type: str = Field(..., description="File type")
    file_size: int = Field(..., description="File size in bytes")
    text_length: int = Field(..., description="Total extracted text length")
    chunk_count: int = Field(..., description="Number of chunks created")
    processing_time_ms: float = Field(..., description="Processing time in milliseconds")
    category: str = Field(..., description="Knowledge category")
    version: str = Field(..., description="Document version")
    review_status: str = Field(..., description="Review status (pending, approved, rejected)")
    uploaded_at: datetime = Field(..., description="Upload timestamp")
    success: bool = Field(..., description="Whether upload was successful")
    message: str = Field(..., description="Status message")


class DeleteDocumentRequest(BaseModel):
    """Request to delete a document."""

    document_id: str = Field(..., description="Document ID to delete")


class DeleteDocumentResponse(BaseModel):
    """Response for document deletion."""

    document_id: str = Field(..., description="Document ID")
    success: bool = Field(..., description="Whether deletion was successful")
    message: str = Field(..., description="Status message")


class ReplaceDocumentVersionRequest(BaseModel):
    """Request to replace document version."""

    old_document_id: str = Field(..., description="Old document ID to replace")
    file_data: str = Field(..., description="Base64-encoded new file data")
    filename: str = Field(..., description="New filename")
    file_type: str = Field(..., description="File type (pdf, docx, txt, md, html)")
    category: str = Field(..., description="Knowledge category")
    version: str = Field(..., description="New version")


class ReplaceDocumentVersionResponse(BaseModel):
    """Response for document version replacement."""

    old_document_id: str = Field(..., description="Old document ID")
    new_document_id: str = Field(..., description="New document ID")
    success: bool = Field(..., description="Whether replacement was successful")
    message: str = Field(..., description="Status message")


class ReviewDocumentRequest(BaseModel):
    """Request to review a document."""

    document_id: str = Field(..., description="Document ID to review")
    review_status: str = Field(..., description="Review status (approved, rejected)")
    review_notes: str | None = Field(default=None, description="Optional review notes")


class ReviewDocumentResponse(BaseModel):
    """Response for document review."""

    document_id: str = Field(..., description="Document ID")
    review_status: str = Field(..., description="Updated review status")
    review_notes: str | None = Field(default=None, description="Review notes")
    success: bool = Field(..., description="Whether review was successful")
    message: str = Field(..., description="Status message")


class SupportedFileTypesResponse(BaseModel):
    """Response with supported file types."""

    file_types: list[str] = Field(..., description="List of supported file types")


class KnowledgeCategoriesResponse(BaseModel):
    """Response with knowledge categories."""

    categories: list[str] = Field(..., description="List of knowledge categories")
