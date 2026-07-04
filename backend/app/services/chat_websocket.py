import asyncio
import logging
import time
from collections import deque
from uuid import UUID

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect, WebSocketState

from app.core.config import settings
from app.schemas.chat_ws import ChatWsEvent, ChatWsMessageType

logger = logging.getLogger(__name__)

NORMAL_CLOSURE = 1000
TRY_AGAIN_LATER = 1013


class ChatConnectionManager:
    """Tracks active chat WebSocket clients per conversation."""

    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = {}
        self._conversation_by_socket: dict[WebSocket, UUID] = {}
        self._heartbeat_tasks: dict[WebSocket, asyncio.Task] = {}
        self._last_pong: dict[WebSocket, float] = {}
        self._ping_sent: dict[WebSocket, float] = {}
        self._sequence_by_conversation: dict[str, int] = {}
        self._event_history: dict[str, deque[ChatWsEvent]] = {}
        self._lock = asyncio.Lock()
        self._shutting_down = False

    async def connect(
        self,
        websocket: WebSocket,
        conversation_id: UUID,
        *,
        last_sequence: int | None = None,
    ) -> bool:
        async with self._lock:
            if self._shutting_down:
                await websocket.close(code=TRY_AGAIN_LATER, reason="Server shutting down")
                return False
            if self.active_connection_count >= settings.chat_ws_max_connections:
                await websocket.close(code=TRY_AGAIN_LATER, reason="Connection limit reached")
                return False

        await websocket.accept()
        key = str(conversation_id)
        now = time.monotonic()
        self._last_pong[websocket] = now
        async with self._lock:
            self._connections.setdefault(key, set()).add(websocket)
            self._conversation_by_socket[websocket] = conversation_id
        self._heartbeat_tasks[websocket] = asyncio.create_task(
            self._heartbeat_loop(websocket, conversation_id),
        )
        await self.send_to(
            websocket,
            ChatWsEvent(
                event="connected",
                conversation_id=conversation_id,
                payload={"message": "WebSocket connected"},
            ),
        )
        if last_sequence is not None:
            await self.replay_since(websocket, conversation_id, last_sequence)
        return True

    @property
    def active_connection_count(self) -> int:
        return sum(len(sockets) for sockets in self._connections.values())

    async def disconnect(self, websocket: WebSocket, conversation_id: UUID) -> None:
        task = self._heartbeat_tasks.pop(websocket, None)
        if task and task is not asyncio.current_task() and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        self._last_pong.pop(websocket, None)
        self._ping_sent.pop(websocket, None)
        self._conversation_by_socket.pop(websocket, None)

        key = str(conversation_id)
        async with self._lock:
            sockets = self._connections.get(key)
            if sockets:
                sockets.discard(websocket)
                if not sockets:
                    del self._connections[key]

        if websocket.client_state == WebSocketState.CONNECTED:
            try:
                await websocket.close()
            except RuntimeError:
                pass

    async def broadcast(self, conversation_id: UUID, event: ChatWsEvent) -> None:
        event = await self._store_event(conversation_id, event)
        key = str(conversation_id)
        async with self._lock:
            sockets = list(self._connections.get(key, set()))

        stale: list[WebSocket] = []
        for websocket in sockets:
            try:
                await self.send_to(websocket, event)
            except (WebSocketDisconnect, RuntimeError):
                stale.append(websocket)

        for websocket in stale:
            await self.disconnect(websocket, conversation_id)

    async def send_to(self, websocket: WebSocket, event: ChatWsEvent) -> None:
        if websocket.client_state != WebSocketState.CONNECTED:
            return
        await websocket.send_json(self._event_to_wire(event))

    async def replay_since(
        self,
        websocket: WebSocket,
        conversation_id: UUID,
        last_sequence: int,
    ) -> None:
        key = str(conversation_id)
        async with self._lock:
            events = [
                event
                for event in self._event_history.get(key, deque())
                if event.sequence is not None and event.sequence > last_sequence
            ]
        for event in events:
            await self.send_to(websocket, event)

    async def handle_client_message(
        self,
        websocket: WebSocket,
        conversation_id: UUID,
        data: dict,
    ) -> None:
        event_type = data.get("event")
        protocol_type = data.get("type")

        if event_type == "pong":
            self._last_pong[websocket] = time.monotonic()
            return
        if protocol_type == "message" and data.get("payload", {}).get("event") == "pong":
            self._last_pong[websocket] = time.monotonic()
            return
        if event_type == "ping":
            await self.send_to(
                websocket,
                ChatWsEvent(event="pong", conversation_id=conversation_id),
            )
            return
        if protocol_type == "read_receipt":
            await self.broadcast(
                conversation_id,
                ChatWsEvent(
                    event="read_receipt",
                    conversation_id=conversation_id,
                    payload=data.get("payload", {}),
                ),
            )
            return
        if protocol_type == "typing":
            await self.broadcast(
                conversation_id,
                ChatWsEvent(
                    event="typing_start",
                    conversation_id=conversation_id,
                    payload=data.get("payload", {}),
                ),
            )

    async def _heartbeat_loop(
        self,
        websocket: WebSocket,
        conversation_id: UUID,
    ) -> None:
        interval = settings.chat_ws_heartbeat_interval_seconds
        timeout = settings.chat_ws_pong_timeout_seconds

        try:
            while websocket.client_state == WebSocketState.CONNECTED:
                await asyncio.sleep(interval)
                if websocket.client_state != WebSocketState.CONNECTED:
                    break

                sent_at = time.monotonic()
                self._ping_sent[websocket] = sent_at
                await self.send_to(
                    websocket,
                    ChatWsEvent(event="ping", conversation_id=conversation_id),
                )

                await asyncio.sleep(timeout)
                last_pong = self._last_pong.get(websocket, 0.0)
                if last_pong < sent_at:
                    logger.info(
                        "Chat WebSocket heartbeat timeout for conversation %s",
                        conversation_id,
                    )
                    break
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "Chat WebSocket heartbeat failed for conversation %s",
                conversation_id,
            )
        finally:
            await self.disconnect(websocket, conversation_id)

    async def close_all(
        self,
        *,
        code: int = NORMAL_CLOSURE,
        reason: str = "Server shutting down",
    ) -> None:
        self._shutting_down = True
        async with self._lock:
            sockets = list(self._conversation_by_socket.keys())
            conversations = dict(self._conversation_by_socket)

        tasks = [
            self._close_socket(websocket, conversations[websocket], code, reason)
            for websocket in sockets
        ]
        if not tasks:
            return

        try:
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=settings.chat_ws_shutdown_timeout_seconds,
            )
        except TimeoutError:
            logger.warning("Timed out while closing chat WebSocket connections")

    async def _close_socket(
        self,
        websocket: WebSocket,
        conversation_id: UUID,
        code: int,
        reason: str,
    ) -> None:
        if websocket.client_state == WebSocketState.CONNECTED:
            try:
                await websocket.close(code=code, reason=reason)
            except RuntimeError:
                pass
        await self.disconnect(websocket, conversation_id)

    async def _store_event(
        self,
        conversation_id: UUID,
        event: ChatWsEvent,
    ) -> ChatWsEvent:
        key = str(conversation_id)
        async with self._lock:
            sequence = self._sequence_by_conversation.get(key, 0) + 1
            self._sequence_by_conversation[key] = sequence
            stored = event.model_copy(update={"sequence": sequence})
            history = self._event_history.setdefault(
                key,
                deque(maxlen=settings.chat_ws_replay_buffer_size),
            )
            history.append(stored)
            return stored

    def _event_to_wire(self, event: ChatWsEvent) -> dict:
        payload = dict(event.payload)
        message_type = self._protocol_type_for_event(event.event)

        if event.event.startswith("typing_"):
            payload.setdefault("status", event.event.replace("typing_", ""))
        elif event.event == "still_working":
            message_type = "typing"
            payload.setdefault("status", "still_working")
        elif event.event in {"connected", "ping", "pong", "error"}:
            payload.setdefault("event", event.event)

        wire = {
            "type": message_type,
            "payload": payload,
            "timestamp": event.timestamp.isoformat(),
            "sequence": event.sequence,
            # Legacy fields keep the existing frontend and /ws/v1/chat clients working.
            "event": event.event,
            "conversation_id": str(event.conversation_id) if event.conversation_id else None,
        }
        return wire

    def _protocol_type_for_event(self, event_type: str) -> ChatWsMessageType:
        if event_type in {"typing_start", "typing_stop", "still_working"}:
            return "typing"
        if event_type == "read_receipt":
            return "read_receipt"
        return "message"


_manager: ChatConnectionManager | None = None


def get_chat_connection_manager() -> ChatConnectionManager:
    global _manager
    if _manager is None:
        _manager = ChatConnectionManager()
    return _manager
