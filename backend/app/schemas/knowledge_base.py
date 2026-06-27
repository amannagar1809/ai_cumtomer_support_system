"""Knowledge base schemas."""

from pydantic import BaseModel, Field


class UploadDocumentRequest(BaseModel):
    """Request to upload a document."""

    file_data: str = Field(..., description="Base64-encoded file data")
    filename: str = Field(..., description="Original filename")
    file_type: str = Field(..., description="File type (pdf, docx, txt, md, html)")


class UploadDocumentResponse(BaseModel):
    """Response for document upload."""

    document_id: str = Field(..., description="Document ID")
    filename: str = Field(..., description="Original filename")
    file_type: str = Field(..., description="File type")
    file_size: int = Field(..., description="File size in bytes")
    text_length: int = Field(..., description="Total extracted text length")
    chunk_count: int = Field(..., description="Number of chunks created")
    processing_time_ms: float = Field(..., description="Processing time in milliseconds")
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


class SupportedFileTypesResponse(BaseModel):
    """Response with supported file types."""

    file_types: list[str] = Field(..., description="List of supported file types")
