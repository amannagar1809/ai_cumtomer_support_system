const API_BASE = "/api/v1";

export class TicketPanel {
  constructor(session, rootEl) {
    this.session = session;
    this.rootEl = rootEl;
    this.tickets = [];
    this.eventSource = null;
    this.visible = false;
    this.render();
    this.connectEvents();
  }

  updateSession(session) {
    this.session = session;
    if (this.visible) {
      this.reconnectEvents();
    }
  }

  render() {
    this.rootEl.innerHTML = `
      <div class="ticket-panel hidden" id="ticket-panel">
        <div class="ticket-panel-header">
          <h3>My Tickets</h3>
          <button type="button" id="ticket-panel-close" aria-label="Close tickets">×</button>
        </div>
        <div class="ticket-lookup">
          <input id="ticket-lookup-input" type="text" placeholder="Enter ticket ID..." />
          <button type="button" id="ticket-lookup-btn">Check status</button>
        </div>
        <div class="ticket-lookup-result hidden" id="ticket-lookup-result"></div>
        <div class="ticket-list" id="ticket-list"></div>
      </div>
    `;
    this.panel = document.getElementById("ticket-panel");
    this.listEl = document.getElementById("ticket-list");
    this.lookupInput = document.getElementById("ticket-lookup-input");
    this.lookupResult = document.getElementById("ticket-lookup-result");

    document.getElementById("ticket-panel-close").addEventListener("click", () => {
      this.hide();
    });
    document.getElementById("ticket-lookup-btn").addEventListener("click", () => {
      this.lookupTicket();
    });
    this.lookupInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        this.lookupTicket();
      }
    });
  }

  connectEvents() {
    if (!this.session?.anonymous_user_id) return;
    this.disconnectEvents();
    const url = `${API_BASE}/chat/tickets/events/stream?anonymous_user_id=${this.session.anonymous_user_id}`;
    this.eventSource = new EventSource(url);
    this.eventSource.addEventListener("ticket.status_changed", (event) => {
      try {
        const data = JSON.parse(event.data);
        this.handleStatusUpdate(data);
      } catch (err) {
        console.error(err);
      }
    });
    this.eventSource.onerror = () => {
      // Browser will auto-reconnect
    };
  }

  reconnectEvents() {
    this.disconnectEvents();
    this.connectEvents();
  }

  disconnectEvents() {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
  }

  handleStatusUpdate(data) {
    const idx = this.tickets.findIndex((t) => t.ticket_id === data.ticket_id);
    if (idx >= 0) {
      this.tickets[idx].status = data.status;
      this.tickets[idx].priority = data.priority;
      this.tickets[idx].can_reopen = ["closed", "resolved"].includes(data.status);
      this.renderList();
      this.flashTicket(data.ticket_id);
    }
  }

  flashTicket(ticketId) {
    const card = this.listEl.querySelector(`[data-ticket-id="${ticketId}"]`);
    if (card) {
      card.classList.add("ticket-updated");
      setTimeout(() => card.classList.remove("ticket-updated"), 2000);
    }
  }

  async show() {
    if (!this.session) return;
    this.panel.classList.remove("hidden");
    this.visible = true;
    await this.loadTickets();
    this.connectEvents();
  }

  hide() {
    this.panel.classList.add("hidden");
    this.visible = false;
    this.disconnectEvents();
  }

  toggle() {
    if (this.visible) {
      this.hide();
    } else {
      this.show();
    }
  }

  async loadTickets() {
    this.listEl.innerHTML = `<p class="ticket-loading">Loading tickets...</p>`;
    try {
      const res = await fetch(
        `${API_BASE}/chat/tickets?anonymous_user_id=${this.session.anonymous_user_id}`,
      );
      if (!res.ok) throw new Error("Failed to load tickets");
      const data = await res.json();
      this.tickets = data.tickets || [];
      this.renderList();
    } catch (err) {
      this.listEl.innerHTML = `<p class="ticket-error">Unable to load tickets.</p>`;
      console.error(err);
    }
  }

  async lookupTicket() {
    const raw = this.lookupInput.value.trim();
    if (!raw) return;
    this.lookupResult.classList.remove("hidden");
    this.lookupResult.innerHTML = `<p class="ticket-loading">Looking up ticket...</p>`;
    try {
      const res = await fetch(
        `${API_BASE}/chat/tickets/${raw}?anonymous_user_id=${this.session.anonymous_user_id}`,
      );
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Ticket not found");
      }
      const ticket = await res.json();
      this.lookupResult.innerHTML = this.ticketCardHtml(ticket, true);
      this.bindReopenButtons(this.lookupResult);
    } catch (err) {
      this.lookupResult.innerHTML = `<p class="ticket-error">${this.escapeHtml(err.message)}</p>`;
    }
  }

  renderList() {
    if (!this.tickets.length) {
      this.listEl.innerHTML = `<p class="ticket-empty">No support tickets yet.</p>`;
      return;
    }
    this.listEl.innerHTML = this.tickets.map((t) => this.ticketCardHtml(t)).join("");
    this.bindReopenButtons(this.listEl);
  }

  ticketCardHtml(ticket, compact = false) {
    const shortId = String(ticket.ticket_id).slice(0, 8);
    const created = `Created: ${new Date(ticket.created_at).toLocaleString()}`;
    const reopenBtn = ticket.can_reopen
      ? `<button type="button" class="btn-reopen-ticket" data-ticket-id="${ticket.ticket_id}">Reopen ticket</button>`
      : "";
    return `
      <article class="ticket-card status-${ticket.status}" data-ticket-id="${ticket.ticket_id}">
        <div class="ticket-card-header">
          <span class="ticket-id">#${shortId}</span>
          <span class="ticket-status-badge">${ticket.status.replace("_", " ")}</span>
        </div>
        <p class="ticket-meta"><strong>Priority:</strong> ${ticket.priority}</p>
        <p class="ticket-meta"><strong>Category:</strong> ${this.escapeHtml(ticket.category)}</p>
        <p class="ticket-meta">${created || ""}</p>
        ${reopenBtn}
        <div class="reopen-form hidden" data-reopen-form="${ticket.ticket_id}">
          <textarea placeholder="Why are you reopening this ticket?" rows="2"></textarea>
          <div class="reopen-actions">
            <button type="button" class="btn-submit-reopen" data-ticket-id="${ticket.ticket_id}">Submit</button>
            <button type="button" class="btn-cancel-reopen" data-ticket-id="${ticket.ticket_id}">Cancel</button>
          </div>
        </div>
      </article>
    `;
  }

  bindReopenButtons(container) {
    container.querySelectorAll(".btn-reopen-ticket").forEach((btn) => {
      btn.addEventListener("click", () => {
        const id = btn.dataset.ticketId;
        const form = container.querySelector(`[data-reopen-form="${id}"]`);
        form?.classList.remove("hidden");
        btn.classList.add("hidden");
      });
    });
    container.querySelectorAll(".btn-cancel-reopen").forEach((btn) => {
      btn.addEventListener("click", () => {
        const id = btn.dataset.ticketId;
        const form = container.querySelector(`[data-reopen-form="${id}"]`);
        form?.classList.add("hidden");
        const reopenBtn = container.querySelector(`.btn-reopen-ticket[data-ticket-id="${id}"]`);
        reopenBtn?.classList.remove("hidden");
      });
    });
    container.querySelectorAll(".btn-submit-reopen").forEach((btn) => {
      btn.addEventListener("click", () => this.submitReopen(btn.dataset.ticketId, container));
    });
  }

  async submitReopen(ticketId, container) {
    const form = container.querySelector(`[data-reopen-form="${ticketId}"]`);
    const textarea = form?.querySelector("textarea");
    const reason = textarea?.value.trim() || "";
    if (reason.length < 3) {
      alert("Please provide a reason (at least 3 characters).");
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/chat/tickets/${ticketId}/reopen`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          anonymous_user_id: this.session.anonymous_user_id,
          reason,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Reopen failed");
      await this.loadTickets();
      alert(data.message || "Ticket reopened.");
    } catch (err) {
      alert(err.message);
    }
  }

  escapeHtml(text) {
    return String(text)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }
}
