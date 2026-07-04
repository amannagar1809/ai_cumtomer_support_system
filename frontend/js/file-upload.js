const API_BASE = "/api/v1";

const DEFAULT_LIMITS = {
  max_file_size_bytes: 10 * 1024 * 1024,
  max_files_per_message: 3,
  chunk_size_bytes: 1024 * 1024,
  allowed_extensions: [".jpg", ".jpeg", ".png", ".pdf", ".txt"],
  allowed_content_types: [
    "image/jpeg",
    "image/jpg",
    "image/png",
    "application/pdf",
    "text/plain",
  ],
};

export class FileUploadManager {
  constructor(session) {
    this.session = session;
    this.limits = null;
    this.pending = [];
  }

  async getLimits() {
    if (this.limits) return this.limits;
    try {
      const res = await fetch(`${API_BASE}/chat/uploads/limits`);
      if (res.ok) {
        this.limits = await res.json();
        return this.limits;
      }
    } catch (err) {
      console.warn("Using default upload limits", err);
    }
    this.limits = DEFAULT_LIMITS;
    return this.limits;
  }

  validateFile(file, limits, currentCount) {
    if (currentCount >= limits.max_files_per_message) {
      return `Maximum ${limits.max_files_per_message} files per message`;
    }
    if (file.size > limits.max_file_size_bytes) {
      return `File must be under ${limits.max_file_size_bytes / (1024 * 1024)}MB`;
    }
    const ext = `.${file.name.split(".").pop()?.toLowerCase() || ""}`;
    if (!limits.allowed_extensions.includes(ext)) {
      return `File type not allowed (${ext})`;
    }
    const type = file.type || "application/octet-stream";
    if (!limits.allowed_content_types.includes(type)) {
      return `Content type not allowed (${type})`;
    }
    return null;
  }

  async uploadFile(file, onProgress) {
    const limits = await this.getLimits();
    const initRes = await fetch(`${API_BASE}/chat/uploads/init`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        anonymous_user_id: this.session.anonymous_user_id,
        conversation_id: this.session.conversation_id,
        filename: file.name,
        content_type: file.type || "application/octet-stream",
        size_bytes: file.size,
      }),
    });
    if (!initRes.ok) {
      const err = await initRes.json().catch(() => ({}));
      throw new Error(err.detail || `Upload init failed (${initRes.status})`);
    }
    const init = await initRes.json();
    const chunkSize = init.chunk_size;
    let uploaded = 0;

    for (const chunk of init.chunks) {
      const start = chunk.chunk_index * chunkSize;
      const end = Math.min(start + chunkSize, file.size);
      const blob = file.slice(start, end);
      let url = chunk.upload_url;
      if (init.storage_provider === "local") {
        const sep = url.includes("?") ? "&" : "?";
        url = `${url}${sep}anonymous_user_id=${this.session.anonymous_user_id}`;
      }
      if (!url.startsWith("http")) {
        url = `${window.location.origin}${url}`;
      }
      const putRes = await fetch(url, {
        method: chunk.method || "PUT",
        body: blob,
        headers: { "Content-Type": file.type || "application/octet-stream" },
      });
      if (!putRes.ok) {
        throw new Error(`Chunk ${chunk.chunk_index + 1} upload failed`);
      }
      uploaded = end;
      if (onProgress) {
        onProgress(Math.round((uploaded / file.size) * 100));
      }
    }

    const completeRes = await fetch(
      `${API_BASE}/chat/uploads/${init.upload_id}/complete`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          anonymous_user_id: this.session.anonymous_user_id,
          conversation_id: this.session.conversation_id,
          upload_id: init.upload_id,
        }),
      },
    );
    if (!completeRes.ok) {
      const err = await completeRes.json().catch(() => ({}));
      throw new Error(err.detail || `Upload complete failed (${completeRes.status})`);
    }
    return completeRes.json();
  }

  createPreview(file, uploaded = null) {
    const item = {
      id: crypto.randomUUID(),
      file,
      uploaded,
      previewUrl: null,
      progress: uploaded ? 100 : 0,
      error: null,
    };
    if (file.type.startsWith("image/")) {
      item.previewUrl = URL.createObjectURL(file);
    } else if (uploaded?.preview_url) {
      item.previewUrl = uploaded.preview_url;
    }
    return item;
  }

  revokePreview(item) {
    if (item.previewUrl?.startsWith("blob:")) {
      URL.revokeObjectURL(item.previewUrl);
    }
  }
}
