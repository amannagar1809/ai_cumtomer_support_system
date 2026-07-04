"""Telegram bot webhook endpoints for receiving updates."""

import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.schemas.telegram import TelegramUpdate
from app.services.telegram_client import TelegramBotClient
from app.services.telegram_commands import TelegramCommandHandler
from app.services.telegram_parser import TelegramMessageParser
from app.services.telegram_user import TelegramUserService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/telegram", tags=["telegram"])

# Initialize services
parser = TelegramMessageParser()
user_service = TelegramUserService()
client = TelegramBotClient()
command_handler = TelegramCommandHandler()


@router.post("/webhook")
async def receive_telegram_webhook(
    payload: dict[str, Any],
    background_tasks: BackgroundTasks,
    request: Request,
) -> dict[str, str]:
    """
    Receive Telegram bot webhook updates.

    This endpoint processes incoming updates from Telegram Bot API.
    """
    if not settings.telegram_enabled:
        logger.warning("Telegram is not enabled, ignoring webhook")
        return {"status": "ignored", "reason": "Telegram not enabled"}

    # Verify webhook secret if configured
    if settings.telegram_webhook_secret:
        secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if secret != settings.telegram_webhook_secret:
            logger.warning("Invalid webhook secret")
            raise HTTPException(status_code=403, detail="Invalid secret token")

    try:
        # Telegram sends updates as a single object, not an array
        update = TelegramUpdate(**payload)

        # Process the update
        if update.message:
            await _process_message(update.message, background_tasks)
        elif update.callback_query:
            await _process_callback_query(update.callback_query, background_tasks)
        elif update.inline_query:
            await _process_inline_query(update.inline_query, background_tasks)

        return {"status": "ok"}

    except Exception as e:
        logger.exception(f"Error processing Telegram webhook: {e}")
        raise HTTPException(status_code=500, detail="Failed to process update")


async def _process_message(message: Any, background_tasks: BackgroundTasks) -> None:
    """Process a Telegram message."""
    try:
        from app.schemas.telegram import TelegramMessage

        telegram_message = TelegramMessage(**message)

        # Parse the message
        parsed_message = parser.parse_message(telegram_message)

        logger.info(
            f"Received Telegram message from user {parsed_message.telegram_user_id}: "
            f"type={parsed_message.message_type}, "
            f"content={parsed_message.content[:50] if parsed_message.content else 'None'}"
        )

        # Handle commands
        if parsed_message.is_command:
            await _handle_command(parsed_message)
        else:
            # Queue regular message for AI processing
            background_tasks.add_task(
                _queue_message_for_processing,
                parsed_message,
            )

    except Exception as e:
        logger.exception(f"Error processing Telegram message: {e}")


async def _handle_command(parsed_message: Any) -> None:
    """Handle bot command."""
    try:
        command = parsed_message.command

        if command == "/start":
            await command_handler.handle_start(
                chat_id=parsed_message.telegram_chat_id,
                telegram_user_id=parsed_message.telegram_user_id,
                first_name=parsed_message.first_name,
            )
        elif command == "/help":
            await command_handler.handle_help(chat_id=parsed_message.telegram_chat_id)
        elif command == "/ticket":
            await command_handler.handle_ticket(
                chat_id=parsed_message.telegram_chat_id,
                telegram_user_id=parsed_message.telegram_user_id,
            )
        elif command == "/status":
            await command_handler.handle_status(
                chat_id=parsed_message.telegram_chat_id,
                telegram_user_id=parsed_message.telegram_user_id,
            )
        else:
            await client.send_message(
                chat_id=parsed_message.telegram_chat_id,
                text=f"Unknown command: {command}\nUse /help to see available commands.",
            )

    except Exception as e:
        logger.exception(f"Error handling command: {e}")


async def _process_callback_query(
    callback_query: dict[str, Any], background_tasks: BackgroundTasks
) -> None:
    """Process a callback query from inline keyboard."""
    try:
        callback_query_id = callback_query.get("id")
        callback_data = callback_query.get("data")
        message = callback_query.get("message", {})
        chat = message.get("chat", {})
        chat_id = chat.get("id")

        logger.info(f"Received callback query: {callback_data}")

        await command_handler.handle_callback_query(
            callback_query_id=callback_query_id,
            callback_data=callback_data,
            chat_id=chat_id,
        )

    except Exception as e:
        logger.exception(f"Error processing callback query: {e}")


async def _process_inline_query(
    inline_query: dict[str, Any], background_tasks: BackgroundTasks
) -> None:
    """Process an inline query."""
    try:
        query_id = inline_query.get("id")
        query = inline_query.get("query", "")

        logger.info(f"Received inline query: {query}")

        # For now, just acknowledge
        # Inline query responses would be implemented for advanced features

    except Exception as e:
        logger.exception(f"Error processing inline query: {e}")


async def _queue_message_for_processing(parsed_message: Any) -> None:
    """
    Queue the parsed Telegram message for AI processing.

    This integrates with the existing message queue system.
    """
    try:
        from app.services.message_queue import MessageQueueService

        queue = MessageQueueService()

        # Get or create conversation
        conversation = await user_service.get_conversation(
            parsed_message.telegram_user_id, parsed_message.telegram_chat_id
        )
        if not conversation:
            conversation = await user_service.create_conversation(
                parsed_message.telegram_user_id, parsed_message.telegram_chat_id
            )

        # Convert to internal message format
        internal_message = {
            "channel": "telegram",
            "telegram_user_id": parsed_message.telegram_user_id,
            "telegram_chat_id": parsed_message.telegram_chat_id,
            "message_id": parsed_message.message_id,
            "message_type": parsed_message.message_type,
            "content": parsed_message.content,
            "attachments": [
                {
                    "file_id": att.file_id,
                    "file_unique_id": att.file_unique_id,
                    "file_size": att.file_size,
                    "mime_type": att.mime_type,
                    "type": att.type,
                }
                for att in parsed_message.attachments
            ],
            "timestamp": parsed_message.timestamp.isoformat(),
            "username": parsed_message.username,
            "first_name": parsed_message.first_name,
            "last_name": parsed_message.last_name,
            "language_code": parsed_message.language_code,
            "conversation_id": str(conversation.id),
        }

        # Add to message queue
        await queue.add_to_queue("telegram_queue", internal_message)

        logger.info(f"Queued Telegram message from {parsed_message.telegram_user_id} for processing")

    except Exception as e:
        logger.exception(f"Error queuing Telegram message for processing: {e}")


@router.post("/set-webhook")
async def set_telegram_webhook() -> dict[str, Any]:
    """Set webhook for Telegram bot."""
    if not settings.telegram_enabled:
        raise HTTPException(status_code=400, detail="Telegram is not enabled")

    if not settings.telegram_webhook_url:
        raise HTTPException(status_code=400, detail="Webhook URL not configured")

    try:
        result = await client.set_webhook(
            webhook_url=settings.telegram_webhook_url,
            secret_token=settings.telegram_webhook_secret,
        )
        return result
    except Exception as e:
        logger.exception(f"Error setting webhook: {e}")
        raise HTTPException(status_code=500, detail="Failed to set webhook")


@router.delete("/webhook")
async def delete_telegram_webhook() -> dict[str, Any]:
    """Delete webhook for Telegram bot."""
    if not settings.telegram_enabled:
        raise HTTPException(status_code=400, detail="Telegram is not enabled")

    try:
        result = await client.delete_webhook()
        return result
    except Exception as e:
        logger.exception(f"Error deleting webhook: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete webhook")


@router.get("/webhook-info")
async def get_webhook_info() -> dict[str, Any]:
    """Get current webhook information."""
    if not settings.telegram_enabled:
        raise HTTPException(status_code=400, detail="Telegram is not enabled")

    try:
        result = await client.get_webhook_info()
        return result
    except Exception as e:
        logger.exception(f"Error getting webhook info: {e}")
        raise HTTPException(status_code=500, detail="Failed to get webhook info")


@router.get("/bot-info")
async def get_bot_info() -> dict[str, Any]:
    """Get bot information."""
    if not settings.telegram_enabled:
        raise HTTPException(status_code=400, detail="Telegram is not enabled")

    try:
        bot_info = await client.get_bot_info()
        return bot_info.model_dump()
    except Exception as e:
        logger.exception(f"Error getting bot info: {e}")
        raise HTTPException(status_code=500, detail="Failed to get bot info")


@router.post("/register-commands")
async def register_bot_commands() -> dict[str, str]:
    """Register bot commands with Telegram."""
    if not settings.telegram_enabled:
        raise HTTPException(status_code=400, detail="Telegram is not enabled")

    try:
        await command_handler.register_commands()
        return {"status": "commands_registered"}
    except Exception as e:
        logger.exception(f"Error registering commands: {e}")
        raise HTTPException(status_code=500, detail="Failed to register commands")


@router.get("/health")
async def telegram_health() -> dict[str, Any]:
    """Check Telegram bot health and configuration."""
    health_status = {
        "enabled": settings.telegram_enabled,
        "configured": bool(settings.telegram_bot_token),
        "webhook_configured": bool(settings.telegram_webhook_url),
        "use_polling": settings.telegram_use_polling,
    }

    if health_status["enabled"] and health_status["configured"]:
        try:
            bot_info = await client.get_bot_info()
            health_status["bot_username"] = bot_info.username
            health_status["bot_id"] = bot_info.id
            health_status["status"] = "healthy"
        except Exception as e:
            health_status["status"] = "error"
            health_status["error"] = str(e)
    else:
        health_status["status"] = "disabled"

    return health_status
