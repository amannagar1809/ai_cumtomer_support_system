"""Mobile push notification service for agent responses."""

import logging
from typing import Any

import httpx

from app.core.config import settings
from app.schemas.mobile_chat import MobilePushNotification, MobilePushToken

logger = logging.getLogger(__name__)


class MobilePushService:
    """Service for sending push notifications to mobile devices."""

    def __init__(self):
        self.firebase_server_key = settings.mobile_firebase_server_key
        self.apns_key_id = settings.mobile_apns_key_id
        self.apns_team_id = settings.mobile_apns_team_id
        self.timeout = 10.0

    async def send_push_notification(
        self,
        token: MobilePushToken,
        notification: MobilePushNotification,
    ) -> bool:
        """
        Send push notification to a device.

        Args:
            token: Device push token information
            notification: Notification payload

        Returns:
            True if sent successfully
        """
        if not settings.mobile_push_notifications_enabled:
            logger.warning("Push notifications are not enabled")
            return False

        try:
            if token.platform == "android":
                return await self._send_fcm_notification(token.token, notification)
            elif token.platform == "ios":
                return await self._send_apns_notification(token.token, notification)
            else:
                logger.warning(f"Unsupported platform: {token.platform}")
                return False

        except Exception as e:
            logger.exception(f"Error sending push notification: {e}")
            return False

    async def _send_fcm_notification(
        self, token: str, notification: MobilePushNotification
    ) -> bool:
        """Send notification via Firebase Cloud Messaging (Android)."""
        if not self.firebase_server_key:
            logger.warning("Firebase server key not configured")
            return False

        url = "https://fcm.googleapis.com/fcm/send"
        headers = {
            "Authorization": f"key={self.firebase_server_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "to": token,
            "notification": {
                "title": notification.title,
                "body": notification.body,
            },
            "data": notification.data,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()

            if result.get("success", 0) > 0:
                logger.info(f"FCM notification sent successfully to {token}")
                return True
            else:
                logger.warning(f"FCM notification failed: {result}")
                return False

    async def _send_apns_notification(
        self, token: str, notification: MobilePushNotification
    ) -> bool:
        """Send notification via Apple Push Notification Service (iOS)."""
        if not self.apns_key_id or not self.apns_team_id:
            logger.warning("APNS credentials not configured")
            return False

        # APNS implementation would require additional libraries like apns2
        # For now, we'll log a warning
        logger.warning("APNS notification not implemented - requires apns2 library")
        return False

    async def send_to_user(
        self,
        user_id: str,
        notification: MobilePushNotification,
    ) -> int:
        """
        Send push notification to all devices for a user.

        Args:
            user_id: User ID
            notification: Notification payload

        Returns:
            Number of devices notified
        """
        # In a real implementation, you would query the database for user's devices
        # For now, we'll return 0
        logger.info(f"Would send push notification to user {user_id}")
        return 0

    async def send_to_conversation(
        self,
        conversation_id: str,
        notification: MobilePushNotification,
    ) -> int:
        """
        Send push notification to all participants in a conversation.

        Args:
            conversation_id: Conversation ID
            notification: Notification payload

        Returns:
            Number of devices notified
        """
        # In a real implementation, you would query the database for conversation participants
        # For now, we'll return 0
        logger.info(f"Would send push notification to conversation {conversation_id}")
        return 0

    async def register_device_token(
        self,
        user_id: str,
        device_id: str,
        platform: str,
        token: str,
        app_version: str | None = None,
    ) -> bool:
        """
        Register a device push token.

        Args:
            user_id: User ID
            device_id: Device ID
            platform: Platform (ios or android)
            token: Push token
            app_version: App version

        Returns:
            True if registered successfully
        """
        # In a real implementation, you would store this in the database
        logger.info(
            f"Registering device token: user_id={user_id}, device_id={device_id}, platform={platform}"
        )
        return True

    async def unregister_device_token(self, device_id: str) -> bool:
        """
        Unregister a device push token.

        Args:
            device_id: Device ID

        Returns:
            True if unregistered successfully
        """
        # In a real implementation, you would remove this from the database
        logger.info(f"Unregistering device token: device_id={device_id}")
        return True
