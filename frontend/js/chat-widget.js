import {
  getOrCreateAnonymousUserId,
  getStoredSession,
  saveSession,
} from "./storage.js";

const API_BASE = "/api/v1";
const INACTIVITY_MS = 30_000;
const PROACTIVE_MESSAGE =
  "Need help? We are here for you. Start a chat anytime.";

class ChatWidget {
  constructor(root) {
    this.root = root;
    this.isOpen = false;
    this.session = null;
    this.inactivityTimer = null;
    this.proactiveShown = false;
    this.render();
    this.bindActivityTracking();
    this.initSession();
  }

  render() {
    this.root.innerHTML = `
      <button class="chat-launcher hidden" id="chat-launcher" aria-label="Open chat">💬</button>
      <div class="chat-proactive-bubble hidden" id="chat-proactive">
        <button class="dismiss" id="chat-proactive-dismiss" aria-label="Dismiss">×</button>
        <p>${PROACTIVE_MESSAGE}</p>
        <button id="chat-proactive-open">Start chat</button>
      </div>
      <section class="chat-panel hidden" id="chat-panel" aria-label="Support chat">
        <header class="chat-header">
          <h2>Customer Support</h2>
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

    this.launcher.addEventListener("click", () => this.open());
    document.getElementById("chat-close").addEventListener("click", () => this.close());
    document.getElementById("chat-proactive-open").addEventListener("click", () => {
      this.hideProactive();
      this.open();
    });
    document.getElementById("chat-proactive-dismiss").addEventListener("click", () => {
      this.hideProactive();
    });
    this.form.addEventListener("submit", (e) => {
      e.preventDefault();
      this.sendLocalMessage();
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

  async initSession() {
    const anonymousUserId = getOrCreateAnonymousUserId();
    const stored = getStoredSession();

    const body = {
      anonymous_user_id: anonymousUserId,
      channel: "web",
      metadata: {
        locale: navigator.language || "en-US",
        page_url: window.location.href,
      },
    };

    if (stored.sessionId && stored.conversationId) {
      body.session_id = stored.sessionId;
      body.conversation_id = stored.conversationId;
    }

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
      saveSession({
        anonymousUserId: this.session.anonymous_user_id,
        sessionId: this.session.session_id,
        conversationId: this.session.conversation_id,
      });

      this.showGreeting(this.session.greeting);
      this.setStatus(
        this.session.resumed
          ? "Welcome back — your session is active."
          : "You are connected. No login required.",
      );
      this.enableInput();
      this.launcher.classList.remove("hidden");
    } catch (err) {
      this.setStatus("Unable to start chat. Please refresh the page.");
      console.error(err);
    }
  }

  showGreeting(greeting) {
    this.messagesEl.innerHTML = "";
    this.appendMessage("ai", greeting.content, greeting.timestamp);
  }

  appendMessage(role, content, timestamp) {
    const el = document.createElement("article");
    el.className = `chat-message ${role}`;
    const time = timestamp ? new Date(timestamp).toLocaleTimeString() : "";
    el.innerHTML = `<p>${this.escapeHtml(content)}</p>${time ? `<time>${time}</time>` : ""}`;
    this.messagesEl.appendChild(el);
    this.messagesEl.scrollTop = this.messagesEl.scrollHeight;
  }

  sendLocalMessage() {
    const text = this.input.value.trim();
    if (!text) return;
    this.appendMessage("user", text, new Date().toISOString());
    this.input.value = "";
    this.setStatus("Message received — AI replies coming in a future story.");
    this.resetInactivityTimer();
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
