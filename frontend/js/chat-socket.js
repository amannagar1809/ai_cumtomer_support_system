const HEARTBEAT_MISS_MS = 45_000;
const RECONNECT_DELAY_MS = 2_000;

export class ChatSocket {
  constructor({ onEvent, onConnectionChange }) {
    this.onEvent = onEvent;
    this.onConnectionChange = onConnectionChange;
    this.socket = null;
    this.session = null;
    this.reconnectTimer = null;
    this.lastServerPingAt = Date.now();
    this.heartbeatWatchTimer = null;
    this.intentionalClose = false;
  }

  connect(session) {
    if (!session?.conversation_id || !session?.session_id || !session?.anonymous_user_id) {
      return;
    }
    this.session = session;
    this.intentionalClose = false;
    this.openSocket();
  }

  disconnect() {
    this.intentionalClose = true;
    clearTimeout(this.reconnectTimer);
    clearInterval(this.heartbeatWatchTimer);
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
    this.onConnectionChange?.("disconnected");
  }

  updateSession(session) {
    this.session = session;
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      this.connect(session);
    }
  }

  openSocket() {
    if (!this.session) return;

    const params = new URLSearchParams({
      conversation_id: this.session.conversation_id,
      session_id: this.session.session_id,
      anonymous_user_id: this.session.anonymous_user_id,
    });
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${protocol}//${window.location.host}/ws/v1/chat?${params}`;

    this.socket = new WebSocket(url);
    this.onConnectionChange?.("connecting");

    this.socket.addEventListener("open", () => {
      this.lastServerPingAt = Date.now();
      this.startHeartbeatWatch();
      this.onConnectionChange?.("connected");
    });

    this.socket.addEventListener("message", (event) => {
      this.lastServerPingAt = Date.now();
      try {
        const data = JSON.parse(event.data);
        this.handleServerEvent(data);
      } catch (err) {
        console.error(err);
      }
    });

    this.socket.addEventListener("close", () => {
      clearInterval(this.heartbeatWatchTimer);
      this.onConnectionChange?.("disconnected");
      if (!this.intentionalClose) {
        this.scheduleReconnect();
      }
    });

    this.socket.addEventListener("error", () => {
      this.onConnectionChange?.("error");
    });
  }

  handleServerEvent(data) {
    const event = data.event;
    if (event === "ping") {
      this.lastServerPingAt = Date.now();
      this.send({ event: "pong" });
      return;
    }
    if (event === "connected") {
      this.lastServerPingAt = Date.now();
    }
    this.onEvent?.(data);
  }

  send(payload) {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(payload));
    }
  }

  startHeartbeatWatch() {
    clearInterval(this.heartbeatWatchTimer);
    this.heartbeatWatchTimer = setInterval(() => {
      const elapsed = Date.now() - this.lastServerPingAt;
      if (elapsed > HEARTBEAT_MISS_MS) {
        this.onConnectionChange?.("stale");
        this.socket?.close();
      }
    }, 5_000);
  }

  scheduleReconnect() {
    clearTimeout(this.reconnectTimer);
    this.reconnectTimer = setTimeout(() => {
      if (!this.intentionalClose && this.session) {
        this.openSocket();
      }
    }, RECONNECT_DELAY_MS);
  }
}
