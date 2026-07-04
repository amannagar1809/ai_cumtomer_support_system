"""Document processing service for knowledge base."""

import base64
import hashlib
import logging
import re
from datetime import datetime
from enum import Enum
from io import BytesIO
from typing import Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Supported file types
SUPPORTED_FILE_TYPES = ["pdf", "docx", "txt", "md", "html"]

# Knowledge base categories
CATEGORY_PRODUCTS = "products"
CATEGORY_POLICIES = "policies"
CATEGORY_FAQS = "faqs"
CATEGORY_TROUBLESHOOTING = "troubleshooting"
CATEGORY_PROCESSES = "processes"

KNOWLEDGE_CATEGORIES = [
    CATEGORY_PRODUCTS,
    CATEGORY_POLICIES,
    CATEGORY_FAQS,
    CATEGORY_TROUBLESHOOTING,
    CATEGORY_PROCESSES,
]

# Document review status
REVIEW_STATUS_PENDING = "pending"
REVIEW_STATUS_APPROVED = "approved"
REVIEW_STATUS_REJECTED = "rejected"

REVIEW_STATUSES = [
    REVIEW_STATUS_PENDING,
    REVIEW_STATUS_APPROVED,
    REVIEW_STATUS_REJECTED,
]

# Chunking parameters
CHUNK_MIN_SIZE = 500
CHUNK_MAX_SIZE = 1000
CHUNK_OVERLAP = 200

# Embedding model
EMBEDDING_MODEL = "text-embedding-ada-002"  # OpenAI
EMBEDDING_DIMENSION = 1536  # OpenAI ada-002 dimension


class FileType(str, Enum):
    """Supported file types."""

    pdf = "pdf"
    docx = "docx"
    txt = "txt"
    md = "md"
    html = "html"


class DocumentChunk(BaseModel):
    """A chunk of text from a document."""

    chunk_id: str = Field(description="Unique chunk ID")
    document_id: str = Field(description="Document ID")
    chunk_index: int = Field(description="Chunk index in document")
    text: str = Field(description="Chunk text content")
    start_char: int = Field(description="Start character position")
    end_char: int = Field(description="End character position")
    embedding: Optional[list[float]] = Field(default=None, description="Text embedding vector")
    # Metadata
    source_document: str = Field(description="Source document filename")
    category: str = Field(description="Knowledge category (products, policies, faqs, troubleshooting, processes)")
    version: str = Field(default="1.0", description="Document version")
    last_updated: datetime = Field(default_factory=datetime.utcnow, description="Last updated timestamp")


class DocumentMetadata(BaseModel):
    """Metadata about a processed document."""

    document_id: str = Field(description="Document ID")
    filename: str = Field(description="Original filename")
    file_type: str = Field(description="File type (pdf, docx, txt, md, html)")
    file_size: int = Field(description="File size in bytes")
    text_length: int = Field(description="Total extracted text length")
    chunk_count: int = Field(description="Number of chunks created")
    processing_time_ms: float = Field(description="Processing time in milliseconds")
    # Additional metadata
    category: str = Field(description="Knowledge category")
    version: str = Field(default="1.0", description="Document version")
    review_status: str = Field(default=REVIEW_STATUS_PENDING, description="Review status (pending, approved, rejected)")
    uploaded_at: datetime = Field(default_factory=datetime.utcnow, description="Upload timestamp")


class DocumentProcessor:
    """Service for processing uploaded documents."""

    def __init__(self, embedding_model: str = EMBEDDING_MODEL):
        """
        Initialize document processor.

        Args:
            embedding_model: Embedding model to use
        """
        self.logger = logger
        self.embedding_model = embedding_model
        self._initialize_embedding_client()

    def _initialize_embedding_client(self):
        """Initialize the embedding client."""
        try:
            # Placeholder for actual embedding client initialization
            # In production, this would initialize OpenAI client or local model
            logger.info(f"Embedding client initialized: {self.embedding_model} (placeholder mode)")
            self.embedding_client = "placeholder"
        except Exception as e:
            logger.error(f"Failed to initialize embedding client: {e}")
            self.embedding_client = None

    def process_document(
        self,
        file_data: bytes,
        filename: str,
        file_type: str,
        category: str,
        version: str = "1.0",
        document_id: Optional[str] = None,
    ) -> tuple[list[DocumentChunk], DocumentMetadata]:
        """
        Process a document: extract text, clean, chunk, and generate embeddings.

        Args:
            file_data: File data as bytes
            filename: Original filename
            file_type: File type (pdf, docx, txt, md, html)
            category: Knowledge category (products, policies, faqs, troubleshooting, processes)
            version: Document version
            document_id: Document ID (generated if not provided)

        Returns:
            Tuple of (chunks, metadata)
        """
        import time

        start_time = time.time()

        # Validate category
        if category not in KNOWLEDGE_CATEGORIES:
            raise ValueError(f"Invalid category. Must be one of: {', '.join(KNOWLEDGE_CATEGORIES)}")

        # Generate document ID if not provided
        if not document_id:
            document_id = self._generate_document_id(file_data, filename)

        # Extract text from document
        text = self._extract_text(file_data, file_type)

        # Clean extracted text
        cleaned_text = self._clean_text(text)

        # Split into chunks with metadata
        chunks = self._split_into_chunks(
            cleaned_text,
            document_id,
            filename,
            category,
            version,
        )

        # Generate embeddings for each chunk
        chunks_with_embeddings = self._generate_embeddings(chunks)

        # Create metadata
        processing_time_ms = (time.time() - start_time) * 1000
        metadata = DocumentMetadata(
            document_id=document_id,
            filename=filename,
            file_type=file_type,
            file_size=len(file_data),
            text_length=len(cleaned_text),
            chunk_count=len(chunks_with_embeddings),
            processing_time_ms=processing_time_ms,
            category=category,
            version=version,
            review_status=REVIEW_STATUS_PENDING,
        )

        logger.info(
            f"Document processed: {filename}, "
            f"category: {category}, "
            f"version: {version}, "
            f"chunks: {len(chunks_with_embeddings)}, "
            f"time: {processing_time_ms:.2f}ms"
        )

        return chunks_with_embeddings, metadata

    def _generate_document_id(self, file_data: bytes, filename: str) -> str:
        """
        Generate a unique document ID.

        Args:
            file_data: File data
            filename: Filename

        Returns:
            Document ID
        """
        # Generate hash from file data and filename
        hash_input = f"{filename}:{len(file_data)}"
        return hashlib.md5(hash_input.encode()).hexdigest()

    def _extract_text(self, file_data: bytes, file_type: str) -> str:
        """
        Extract text from document.

        Args:
            file_data: File data as bytes
            file_type: File type (pdf, docx, txt, md, html)

        Returns:
            Extracted text
        """
        try:
            if file_type == "pdf":
                return self._extract_text_from_pdf(file_data)
            elif file_type == "docx":
                return self._extract_text_from_docx(file_data)
            elif file_type == "txt":
                return self._extract_text_from_txt(file_data)
            elif file_type == "md":
                return self._extract_text_from_txt(file_data)  # Markdown is plain text
            elif file_type == "html":
                return self._extract_text_from_html(file_data)
            else:
                raise ValueError(f"Unsupported file type: {file_type}")
        except Exception as e:
            logger.error(f"Failed to extract text from {file_type}: {e}")
            raise

    def _extract_text_from_pdf(self, file_data: bytes) -> str:
        """
        Extract text from PDF using PyPDF2.

        Args:
            file_data: PDF file data

        Returns:
            Extracted text
        """
        # Placeholder implementation
        # In production, this would use PyPDF2 or pdfplumber
        # For now, return placeholder text
        return "Placeholder text extracted from PDF file."

    def _extract_text_from_docx(self, file_data: bytes) -> str:
        """
        Extract text from DOCX using docx2txt.

        Args:
            file_data: DOCX file data

        Returns:
            Extracted text
        """
        # Placeholder implementation
        # In production, this would use docx2txt or python-docx
        # For now, return placeholder text
        return "Placeholder text extracted from DOCX file."

    def _extract_text_from_txt(self, file_data: bytes) -> str:
        """
        Extract text from TXT file.

        Args:
            file_data: TXT file data

        Returns:
            Extracted text
        """
        try:
            return file_data.decode("utf-8")
        except UnicodeDecodeError:
            # Try with different encoding
            return file_data.decode("latin-1")

    def _extract_text_from_html(self, file_data: bytes) -> str:
        """
        Extract text from HTML using BeautifulSoup.

        Args:
            file_data: HTML file data

        Returns:
            Extracted text
        """
        # Placeholder implementation
        # In production, this would use BeautifulSoup
        # For now, return placeholder text
        return "Placeholder text extracted from HTML file."

    def _clean_text(self, text: str) -> str:
        """
        Clean extracted text: remove headers/footers, normalize spacing.

        Args:
            text: Raw extracted text

        Returns:
            Cleaned text
        """
        # Remove excessive whitespace
        text = re.sub(r"\s+", " ", text)

        # Remove common header/footer patterns
        # Page numbers
        text = re.sub(r"\n\s*\d+\s*\n", "\n", text)
        # Common footer patterns
        text = re.sub(r"Page \d+ of \d+", "", text)
        text = re.sub(r"Confidential", "", text, flags=re.IGNORECASE)

        # Normalize line breaks
        text = re.sub(r"\n\s*\n", "\n\n", text)

        # Trim leading/trailing whitespace
        text = text.strip()

        return text

    def _split_into_chunks(
        self,
        text: str,
        document_id: str,
        filename: str,
        category: str,
        version: str,
    ) -> list[DocumentChunk]:
        """
        Split text into chunks with overlap and metadata.

        Args:
            text: Text to split
            document_id: Document ID
            filename: Source document filename
            category: Knowledge category
            version: Document version

        Returns:
            List of document chunks
        """
        chunks = []
        start = 0
        chunk_index = 0

        while start < len(text):
            # Calculate end position
            end = min(start + CHUNK_MAX_SIZE, len(text))

            # If chunk is too small and not at end, extend it
            if end - start < CHUNK_MIN_SIZE and end < len(text):
                end = min(start + CHUNK_MIN_SIZE, len(text))

            # Extract chunk text
            chunk_text = text[start:end]

            # Generate chunk ID
            chunk_id = f"{document_id}_chunk_{chunk_index}"

            # Create chunk with metadata
            chunk = DocumentChunk(
                chunk_id=chunk_id,
                document_id=document_id,
                chunk_index=chunk_index,
                text=chunk_text,
                start_char=start,
                end_char=end,
                embedding=None,
                source_document=filename,
                category=category,
                version=version,
                last_updated=datetime.utcnow(),
            )

            chunks.append(chunk)

            # Move to next chunk with overlap
            start = end - CHUNK_OVERLAP
            if start >= end:  # Prevent infinite loop
                start = end

            chunk_index += 1

        logger.info(f"Split text into {len(chunks)} chunks with metadata")
        return chunks

    def _generate_embeddings(
        self,
        chunks: list[DocumentChunk],
    ) -> list[DocumentChunk]:
        """
        Generate embeddings for each chunk.

        Args:
            chunks: List of document chunks

        Returns:
            List of chunks with embeddings
        """
        # Placeholder implementation
        # In production, this would:
        # 1. Call OpenAI embedding API or local model
        # 2. Store embedding vector in each chunk
        # For now, add placeholder embeddings
        for chunk in chunks:
            # Placeholder embedding (zeros of correct dimension)
            chunk.embedding = [0.0] * EMBEDDING_DIMENSION

        logger.info(f"Generated embeddings for {len(chunks)} chunks")
        return chunks

    def get_supported_file_types(self) -> list[str]:
        """
        Get list of supported file types.

        Returns:
            List of supported file types
        """
        return SUPPORTED_FILE_TYPES
