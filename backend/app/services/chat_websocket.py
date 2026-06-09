import asyncio
import logging
import time
from uuid import UUID

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect, WebSocketState

from app.core.config import settings
from app.schemas.chat_ws import ChatWsEvent

logger = logging.getLogger(__name__)


class ChatConnectionManager:
    """Tracks active chat WebSocket clients per conversation."""

    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = {}
        self._heartbeat_tasks: dict[WebSocket, asyncio.Task] = {}
        self._last_pong: dict[WebSocket, float] = {}
        self._ping_sent: dict[WebSocket, float] = {}
        self._lock = asyncio.Lock()

    async def connect(
        self,
        websocket: WebSocket,
        conversation_id: UUID,
    ) -> None:
        await websocket.accept()
        key = str(conversation_id)
        now = time.monotonic()
        self._last_pong[websocket] = now
        async with self._lock:
            self._connections.setdefault(key, set()).add(websocket)
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

    async def disconnect(self, websocket: WebSocket, conversation_id: UUID) -> None:
        task = self._heartbeat_tasks.pop(websocket, None)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        self._last_pong.pop(websocket, None)
        self._ping_sent.pop(websocket, None)

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
        await websocket.send_json(event.model_dump(mode="json"))

    async def handle_client_message(
        self,
        websocket: WebSocket,
        conversation_id: UUID,
        data: dict,
    ) -> None:
        event_type = data.get("event")
        if event_type == "pong":
            self._last_pong[websocket] = time.monotonic()
            return
        if event_type == "ping":
            await self.send_to(
                websocket,
                ChatWsEvent(event="pong", conversation_id=conversation_id),
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


_manager: ChatConnectionManager | None = None


def get_chat_connection_manager() -> ChatConnectionManager:
    global _manager
    if _manager is None:
        _manager = ChatConnectionManager()
    return _manager
