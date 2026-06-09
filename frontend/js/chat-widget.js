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
          <button id="chat-close" aria-label="Close chat">×</button>
        </header>
        <div class="chat-messages" id="chat-messages"></div>
        <div class="chat-status" id="chat-status">Connecting...</div>
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

      this.session = {
        session_id: status.session_id,
        conversation_id: status.conversation_id,
        anonymous_user_id: anonymousUserId,
        expires_at: status.expires_at,
        resumed: true,
      };
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
      this.session = {
        session_id: data.session_id,
        conversation_id: data.conversation_id,
        anonymous_user_id: data.anonymous_user_id,
        expires_at: data.expires_at,
        resumed: true,
      };

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

      this.session = await res.json();
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
      this.appendMessage(role, msg.content, msg.timestamp);
    }
  }

  appendMessage(role, content, timestamp) {
    const el = document.createElement("article");
    el.className = `chat-message ${role}`;
    const time = timestamp ? new Date(timestamp).toLocaleTimeString() : "";
    el.innerHTML = `<p>${this.escapeHtml(content)}</p>${time ? `<time>${time}</time>` : ""}`;
    this.messagesEl.appendChild(el);
    this.messagesEl.scrollTop = this.messagesEl.scrollHeight;
  }

  async sendMessage() {
    const text = this.input.value.trim();
    if (!text || !this.session) return;

    this.appendMessage("user", text, new Date().toISOString());
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
          }),
        },
      );
      if (res.ok) {
        const now = new Date().toISOString();
        saveLastConversation(this.session.conversation_id, now);
        this.setHeaderMeta(now);
        this.setStatus("Message received — AI replies coming in a future story.");
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
