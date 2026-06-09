import { FileUploadManager } from "./file-upload.js";
import { TicketPanel } from "./ticket-panel.js";
import {
  clearSession,
  getOrCreateAnonymousUserId,
  getStoredSession,
  saveLastConversation,
  saveSession,
} from "./storage.js";
import { formatLastActiveLabel } from "./time-utils.js";

const API_BASE = "/api/v1";
const INACTIVITY_MS = 30_000;
const PROACTIVE_MESSAGE =
  "Need help? We are here for you. Start a chat anytime.";

class ChatWidget {
  constructor(root) {
    this.root = root;
    this.isOpen = false;
    this.session = null;
    this.returningUser = null;
    this.inactivityTimer = null;
    this.proactiveShown = false;
    this.pendingFiles = [];
    this.uploadManager = null;
    this.ticketPanel = null;
    this.render();
    this.bindActivityTracking();
    this.initSession();
  }

  render() {
    this.root.innerHTML = `
      <div class="chat-continue-banner hidden" id="chat-continue-banner">
        <div class="chat-continue-content">
          <p class="chat-continue-title">Welcome back!</p>
          <p class="chat-continue-subtitle" id="chat-last-active"></p>
          <div class="chat-continue-actions">
            <button type="button" class="btn-continue" id="chat-continue-btn">
              Continue Previous Conversation
            </button>
            <button type="button" class="btn-new-chat" id="chat-new-btn">
              Start New Chat
            </button>
          </div>
        </div>
      </div>
      <button class="chat-launcher hidden" id="chat-launcher" aria-label="Open chat">💬</button>
      <div class="chat-proactive-bubble hidden" id="chat-proactive">
        <button class="dismiss" id="chat-proactive-dismiss" aria-label="Dismiss">×</button>
        <p>${PROACTIVE_MESSAGE}</p>
        <button id="chat-proactive-open">Start chat</button>
      </div>
      <section class="chat-panel hidden" id="chat-panel" aria-label="Support chat">
        <header class="chat-header">
          <div>
            <h2>Customer Support</h2>
            <p class="chat-header-meta hidden" id="chat-header-meta"></p>
          </div>
          <div class="chat-header-actions">
            <button type="button" class="chat-tickets-btn hidden" id="chat-tickets-btn">My Tickets</button>
            <button id="chat-close" aria-label="Close chat">×</button>
          </div>
        </header>
        <div id="ticket-panel-root"></div>
        <div class="chat-messages" id="chat-messages"></div>
        <div class="chat-status" id="chat-status">Connecting...</div>
        <div class="chat-upload-zone hidden" id="chat-upload-zone">
          <p>Drag and drop files here</p>
          <p>JPG, PNG, PDF, TXT · max 10MB · up to 3 files</p>
          <input id="chat-file-input" type="file" multiple accept=".jpg,.jpeg,.png,.pdf,.txt,image/jpeg,image/png,application/pdf,text/plain" />
        </div>
        <div class="chat-upload-toolbar">
          <button type="button" class="chat-attach-btn" id="chat-attach-btn" disabled>Attach file</button>
        </div>
        <div class="chat-file-previews" id="chat-file-previews"></div>
        <form class="chat-input-area" id="chat-form">
          <input id="chat-input" type="text" placeholder="Type a message..." disabled />
          <button type="submit" disabled>Send</button>
        </form>
      </section>
    `;

    this.launcher = document.getElementById("chat-launcher");
    this.panel = document.getElementById("chat-panel");
    this.messagesEl = document.getElementById("chat-messages");
    this.statusEl = document.getElementById("chat-status");
    this.form = document.getElementById("chat-form");
    this.input = document.getElementById("chat-input");
    this.proactive = document.getElementById("chat-proactive");
    this.continueBanner = document.getElementById("chat-continue-banner");
    this.lastActiveEl = document.getElementById("chat-last-active");
    this.headerMeta = document.getElementById("chat-header-meta");
    this.uploadZone = document.getElementById("chat-upload-zone");
    this.fileInput = document.getElementById("chat-file-input");
    this.attachBtn = document.getElementById("chat-attach-btn");
    this.filePreviews = document.getElementById("chat-file-previews");
    this.ticketsBtn = document.getElementById("chat-tickets-btn");
    this.ticketPanelRoot = document.getElementById("ticket-panel-root");

    this.bindUploadHandlers();
    this.ticketsBtn.addEventListener("click", () => {
      this.ticketPanel?.toggle();
    });
    this.launcher.addEventListener("click", () => this.open());
    document.getElementById("chat-close").addEventListener("click", () => this.close());
    document.getElementById("chat-continue-btn").addEventListener("click", () => {
      this.continuePreviousConversation();
    });
    document.getElementById("chat-new-btn").addEventListener("click", () => {
      this.hideContinueBanner();
      this.startNewSession();
    });
    document.getElementById("chat-proactive-open").addEventListener("click", () => {
      this.hideProactive();
      this.open();
    });
    document.getElementById("chat-proactive-dismiss").addEventListener("click", () => {
      this.hideProactive();
    });
    this.form.addEventListener("submit", (e) => {
      e.preventDefault();
      this.sendMessage();
    });
  }

  setSession(session) {
    this.session = session;
    if (session) {
      this.uploadManager = new FileUploadManager(session);
      if (!this.ticketPanel) {
        this.ticketPanel = new TicketPanel(session, this.ticketPanelRoot);
      } else {
        this.ticketPanel.updateSession(session);
      }
    }
  }

  bindUploadHandlers() {
    this.attachBtn.addEventListener("click", () => this.fileInput.click());
    this.fileInput.addEventListener("change", (e) => {
      this.handleFiles(e.target.files);
      e.target.value = "";
    });
    this.uploadZone.addEventListener("dragover", (e) => {
      e.preventDefault();
      this.uploadZone.classList.add("dragover");
    });
    this.uploadZone.addEventListener("dragleave", () => {
      this.uploadZone.classList.remove("dragover");
    });
    this.uploadZone.addEventListener("drop", (e) => {
      e.preventDefault();
      this.uploadZone.classList.remove("dragover");
      this.handleFiles(e.dataTransfer.files);
    });
    this.uploadZone.addEventListener("click", () => this.fileInput.click());
  }

  async handleFiles(fileList) {
    if (!this.uploadManager || !fileList?.length) return;
    const limits = await this.uploadManager.getLimits();
    for (const file of fileList) {
      if (this.pendingFiles.length >= limits.max_files_per_message) {
        this.setStatus(`Maximum ${limits.max_files_per_message} files per message`);
        break;
      }
      const error = this.uploadManager.validateFile(
        file,
        limits,
        this.pendingFiles.length,
      );
      if (error) {
        this.setStatus(error);
        continue;
      }
      const item = this.uploadManager.createPreview(file);
      this.pendingFiles.push(item);
      this.renderFilePreviews();
      this.uploadPendingFile(item);
    }
  }

  async uploadPendingFile(item) {
    try {
      const uploaded = await this.uploadManager.uploadFile(item.file, (pct) => {
        item.progress = pct;
        this.updateFilePreviewProgress(item);
      });
      item.uploaded = uploaded;
      item.progress = 100;
      if (!item.previewUrl && uploaded.preview_url) {
        item.previewUrl = uploaded.preview_url.startsWith("http")
          ? uploaded.preview_url
          : `${window.location.origin}${uploaded.preview_url}`;
      }
      this.renderFilePreviews();
    } catch (err) {
      item.error = err.message;
      this.setStatus(err.message);
      this.renderFilePreviews();
    }
  }

  removePendingFile(id) {
    const idx = this.pendingFiles.findIndex((f) => f.id === id);
    if (idx === -1) return;
    this.uploadManager.revokePreview(this.pendingFiles[idx]);
    this.pendingFiles.splice(idx, 1);
    this.renderFilePreviews();
  }

  renderFilePreviews() {
    this.filePreviews.innerHTML = "";
    for (const item of this.pendingFiles) {
      const el = document.createElement("div");
      el.className = "chat-file-preview";
      const icon = item.file.type.startsWith("image/")
        ? `<img src="${item.previewUrl}" alt="${this.escapeHtml(item.file.name)}" />`
        : `<div class="file-icon">${item.file.type === "application/pdf" ? "PDF" : "TXT"}</div>`;
      el.innerHTML = `
        <button type="button" class="remove-file" aria-label="Remove file">×</button>
        ${icon}
        <span class="file-name">${this.escapeHtml(item.file.name)}</span>
        ${item.progress < 100 && !item.error ? '<div class="progress-bar"><span></span></div>' : ""}
      `;
      el.querySelector(".remove-file").addEventListener("click", () => {
        this.removePendingFile(item.id);
      });
      this.filePreviews.appendChild(el);
      if (item.progress < 100) {
        this.updateFilePreviewProgress(item, el);
      }
    }
  }

  updateFilePreviewProgress(item, el = null) {
    const node =
      el ||
      [...this.filePreviews.querySelectorAll(".chat-file-preview")].find((n) =>
        n.querySelector(".file-name")?.textContent === item.file.name,
      );
    const bar = node?.querySelector(".progress-bar span");
    if (bar) bar.style.width = `${item.progress}%`;
  }

  getReadyAttachments() {
    return this.pendingFiles
      .filter((f) => f.uploaded && !f.error)
      .map((f) => ({
        file_id: f.uploaded.file_id,
        url: f.uploaded.url.startsWith("http")
          ? f.uploaded.url
          : `${window.location.origin}${f.uploaded.url}`,
        filename: f.uploaded.filename,
        content_type: f.uploaded.content_type,
        attachment_type: f.uploaded.attachment_type,
        size_bytes: f.uploaded.size_bytes,
        ocr_requested: ["image", "pdf"].includes(f.uploaded.attachment_type),
      }));
  }

  clearPendingFiles() {
    for (const item of this.pendingFiles) {
      this.uploadManager?.revokePreview(item);
    }
    this.pendingFiles = [];
    this.renderFilePreviews();
  }

  bindActivityTracking() {
    const reset = () => {
      this.resetInactivityTimer();
      if (this.proactiveShown) {
        this.hideProactive();
      }
    };
    ["mousemove", "mousedown", "keydown", "scroll", "touchstart"].forEach((evt) => {
      window.addEventListener(evt, reset, { passive: true });
    });
    this.resetInactivityTimer();
  }

  resetInactivityTimer() {
    clearTimeout(this.inactivityTimer);
    this.inactivityTimer = setTimeout(() => this.showProactive(), INACTIVITY_MS);
  }

  showProactive() {
    if (this.isOpen || this.proactiveShown) return;
    this.proactiveShown = true;
    this.proactive.classList.remove("hidden");
    this.launcher.classList.add("has-notification");
  }

  hideProactive() {
    this.proactiveShown = false;
    this.proactive.classList.add("hidden");
    this.launcher.classList.remove("has-notification");
    this.resetInactivityTimer();
  }

  showContinueBanner(data) {
    this.returningUser = data;
    this.lastActiveEl.textContent = formatLastActiveLabel(data.last_active_at);
    this.continueBanner.classList.remove("hidden");
    this.launcher.classList.remove("hidden");
  }

  hideContinueBanner() {
    this.continueBanner.classList.add("hidden");
  }

  setHeaderMeta(lastActiveAt) {
    const label = formatLastActiveLabel(lastActiveAt);
    if (!label) {
      this.headerMeta.classList.add("hidden");
      return;
    }
    this.headerMeta.textContent = label;
    this.headerMeta.classList.remove("hidden");
  }

  async initSession() {
    const anonymousUserId = getOrCreateAnonymousUserId();
    const stored = getStoredSession();

    if (stored.sessionId && stored.conversationId) {
      const resumed = await this.tryResumeSession(
        anonymousUserId,
        stored.sessionId,
        stored.conversationId,
      );
      if (resumed) return;
      clearSession();
    }

    try {
      const res = await fetch(
        `${API_BASE}/chat/returning-user?anonymous_user_id=${anonymousUserId}`,
      );
      if (res.ok) {
        const data = await res.json();
        if (data.is_returning_user && data.can_continue) {
          saveLastConversation(data.conversation_id, data.last_active_at);
          this.showContinueBanner(data);
          this.setStatus("We found your previous conversation.");
          return;
        }
      }
    } catch (err) {
      console.error(err);
    }

    await this.startNewSession(anonymousUserId, { openOnReady: false });
  }

  async tryResumeSession(anonymousUserId, sessionId, conversationId) {
    try {
      const res = await fetch(
        `${API_BASE}/chat/sessions/${sessionId}?anonymous_user_id=${anonymousUserId}`,
      );
      if (!res.ok) return false;

      const status = await res.json();
      const messagesRes = await fetch(
        `${API_BASE}/chat/conversations/${conversationId}/messages?anonymous_user_id=${anonymousUserId}`,
      );
      const messagesData = messagesRes.ok ? await messagesRes.json() : { messages: [] };

      this.setSession({
        session_id: status.session_id,
        conversation_id: status.conversation_id,
        anonymous_user_id: anonymousUserId,
        expires_at: status.expires_at,
        resumed: true,
      });
      saveSession({
        anonymousUserId,
        sessionId: status.session_id,
        conversationId: status.conversation_id,
        lastActiveAt: new Date().toISOString(),
      });
      saveLastConversation(status.conversation_id, new Date().toISOString());

      this.renderMessages(messagesData.messages);
      this.setStatus("Welcome back — your session is active.");
      this.enableInput();
      this.launcher.classList.remove("hidden");
      return true;
    } catch (err) {
      console.error(err);
      return false;
    }
  }

  async continuePreviousConversation() {
    if (!this.returningUser?.conversation_id) return;

    const anonymousUserId = getOrCreateAnonymousUserId();
    this.setStatus("Loading your previous conversation...");
    this.hideContinueBanner();

    try {
      const res = await fetch(
        `${API_BASE}/chat/conversations/${this.returningUser.conversation_id}/continue`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ anonymous_user_id: anonymousUserId }),
        },
      );

      if (!res.ok) {
        throw new Error(`Continue failed (${res.status})`);
      }

      const data = await res.json();
      this.setSession({
        session_id: data.session_id,
        conversation_id: data.conversation_id,
        anonymous_user_id: data.anonymous_user_id,
        expires_at: data.expires_at,
        resumed: true,
      });

      saveSession({
        anonymousUserId: data.anonymous_user_id,
        sessionId: data.session_id,
        conversationId: data.conversation_id,
        lastActiveAt: data.last_active_at,
      });
      saveLastConversation(data.conversation_id, data.last_active_at);

      this.renderMessages(data.messages);
      this.setHeaderMeta(data.last_active_at);
      this.setStatus("Previous conversation loaded. Context is ready.");
      this.enableInput();
      this.open();
    } catch (err) {
      this.setStatus("Unable to load previous conversation.");
      console.error(err);
      this.launcher.classList.remove("hidden");
    }
  }

  async startNewSession(anonymousUserId = getOrCreateAnonymousUserId(), options = {}) {
    const { openOnReady = true } = options;
    clearSession();

    const body = {
      anonymous_user_id: anonymousUserId,
      channel: "web",
      metadata: {
        locale: navigator.language || "en-US",
        page_url: window.location.href,
      },
    };

    try {
      const res = await fetch(`${API_BASE}/chat/sessions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        throw new Error(`Session init failed (${res.status})`);
      }

      this.setSession(await res.json());
      const now = new Date().toISOString();
      saveSession({
        anonymousUserId: this.session.anonymous_user_id,
        sessionId: this.session.session_id,
        conversationId: this.session.conversation_id,
        lastActiveAt: now,
      });
      saveLastConversation(this.session.conversation_id, now);

      this.renderMessages([this.session.greeting]);
      this.setStatus("You are connected. No login required.");
      this.enableInput();
      this.launcher.classList.remove("hidden");
      if (openOnReady) {
        this.open();
      }
    } catch (err) {
      this.setStatus("Unable to start chat. Please refresh the page.");
      console.error(err);
    }
  }

  renderMessages(messages) {
    this.messagesEl.innerHTML = "";
    for (const msg of messages) {
      const role = msg.role === "customer" ? "user" : msg.role;
      this.appendMessage(role, msg.content, msg.timestamp, msg.attachments || []);
    }
  }

  renderAttachmentHtml(attachments, role) {
    if (!attachments?.length) return "";
    const items = attachments
      .map((a) => {
        const url = a.url?.startsWith("http") ? a.url : `${window.location.origin}${a.url}`;
        if (a.attachment_type === "image") {
          return `<img src="${url}" alt="${this.escapeHtml(a.filename)}" />`;
        }
        return `<span class="attachment-chip">${this.escapeHtml(a.filename)}</span>`;
      })
      .join("");
    return `<div class="chat-message-attachments">${items}</div>`;
  }

  appendMessage(role, content, timestamp, attachments = []) {
    const el = document.createElement("article");
    el.className = `chat-message ${role}`;
    const time = timestamp ? new Date(timestamp).toLocaleTimeString() : "";
    const body = content ? `<p>${this.escapeHtml(content)}</p>` : "";
    el.innerHTML = `${body}${this.renderAttachmentHtml(attachments, role)}${time ? `<time>${time}</time>` : ""}`;
    this.messagesEl.appendChild(el);
    this.messagesEl.scrollTop = this.messagesEl.scrollHeight;
  }

  async sendMessage() {
    const text = this.input.value.trim();
    const attachments = this.getReadyAttachments();
    if ((!text && !attachments.length) || !this.session) return;
    if (this.pendingFiles.some((f) => !f.uploaded && !f.error)) {
      this.setStatus("Please wait for uploads to finish.");
      return;
    }
    if (this.pendingFiles.some((f) => f.error)) {
      this.setStatus("Remove failed uploads before sending.");
      return;
    }

    this.appendMessage("user", text, new Date().toISOString(), attachments);
    this.input.value = "";
    this.resetInactivityTimer();

    try {
      const res = await fetch(
        `${API_BASE}/chat/conversations/${this.session.conversation_id}/messages`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            anonymous_user_id: this.session.anonymous_user_id,
            session_id: this.session.session_id,
            content: text,
            attachments,
          }),
        },
      );
      if (res.ok) {
        const now = new Date().toISOString();
        saveLastConversation(this.session.conversation_id, now);
        this.setHeaderMeta(now);
        this.clearPendingFiles();
        this.setStatus("Message received — AI replies coming in a future story.");
      } else {
        const err = await res.json().catch(() => ({}));
        this.setStatus(err.detail || "Failed to send message.");
      }
    } catch (err) {
      console.error(err);
    }
  }

  setStatus(text) {
    this.statusEl.textContent = text;
  }

  enableInput() {
    this.input.disabled = false;
    this.form.querySelector("button").disabled = false;
    this.attachBtn.disabled = false;
    this.ticketsBtn.classList.remove("hidden");
    this.uploadZone.classList.remove("hidden");
  }

  open() {
    this.isOpen = true;
    this.panel.classList.remove("hidden");
    this.launcher.classList.add("hidden");
    this.hideProactive();
    this.hideContinueBanner();
    this.input.focus();
  }

  close() {
    this.isOpen = false;
    this.panel.classList.add("hidden");
    this.launcher.classList.remove("hidden");
    this.resetInactivityTimer();
  }

  escapeHtml(text) {
    return text
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const root = document.getElementById("chat-widget-root");
  if (root) {
    new ChatWidget(root);
  }
});
