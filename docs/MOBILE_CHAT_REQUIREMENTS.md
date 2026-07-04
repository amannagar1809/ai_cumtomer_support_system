# Mobile Chat Interface Requirements

## Overview
This document outlines the requirements for the mobile app chat interface that integrates with the AI Customer Support System via REST API endpoints.

## API Endpoints

### Base URL
```
https://api.example.com/api/v1/mobile
```

### Authentication
All endpoints require authentication via JWT token in the Authorization header:
```
Authorization: Bearer <token>
```

## Endpoints

### 1. Create Conversation and Send Message
**POST** `/conversations`

Create a new conversation and send the first message.

**Request Body:**
```json
{
  "message": "Hello, I need help with my account",
  "attachments": [],
  "device_id": "device-uuid",
  "app_version": "1.0.0"
}
```

**Response:**
```json
{
  "message_id": "uuid",
  "conversation_id": "uuid",
  "timestamp": "2026-06-18T00:00:00Z",
  "status": "sent"
}
```

### 2. Send Message to Existing Conversation
**POST** `/conversations/{conversation_id}/messages`

Send a message to an existing conversation.

**Request Body:**
```json
{
  "message": "I have a question about billing",
  "attachments": [],
  "device_id": "device-uuid",
  "app_version": "1.0.0"
}
```

**Response:**
```json
{
  "message_id": "uuid",
  "conversation_id": "uuid",
  "timestamp": "2026-06-18T00:00:00Z",
  "status": "sent"
}
```

### 3. Get Messages (Pagination)
**POST** `/conversations/{conversation_id}/messages/get`

Retrieve messages from a conversation with pagination.

**Request Body:**
```json
{
  "since": "2026-06-18T00:00:00Z",
  "limit": 50,
  "offset": 0
}
```

**Response:**
```json
{
  "messages": [
    {
      "id": "uuid",
      "conversation_id": "uuid",
      "sender_type": "customer",
      "message": "Hello",
      "timestamp": "2026-06-18T00:00:00Z",
      "language": "en",
      "sentiment": "neutral",
      "is_read": false,
      "attachments": []
    }
  ],
  "conversation_id": "uuid",
  "has_more": true,
  "last_timestamp": "2026-06-18T00:00:00Z"
}
```

### 4. Long-Poll for New Messages
**POST** `/conversations/{conversation_id}/messages/poll`

Long-poll endpoint for real-time message updates (fallback for poor network).

**Request Body:**
```json
{
  "last_message_id": "uuid",
  "timeout": 30
}
```

**Response:**
```json
{
  "messages": [],
  "conversation_id": "uuid",
  "timeout_reached": true
}
```

### 5. Get Conversations List
**GET** `/conversations?limit=20&offset=0`

Get list of user's conversations.

**Response:**
```json
{
  "conversations": [
    {
      "id": "uuid",
      "user_id": "uuid",
      "channel": "web",
      "status": "active",
      "started_at": "2026-06-18T00:00:00Z",
      "last_message_at": "2026-06-18T00:00:00Z",
      "message_count": 10,
      "unread_count": 2
    }
  ],
  "total": 1,
  "has_more": false
}
```

### 6. Sync Offline Messages
**POST** `/sync`

Sync offline messages from device when connection is restored.

**Request Body:**
```json
{
  "device_id": "device-uuid",
  "offline_messages": [
    {
      "id": "local-uuid",
      "conversation_id": "uuid",
      "message": "Offline message",
      "timestamp": "2026-06-18T00:00:00Z",
      "device_id": "device-uuid",
      "attachments": []
    }
  ],
  "last_sync_timestamp": "2026-06-18T00:00:00Z"
}
```

**Response:**
```json
{
  "synced_message_ids": ["local-uuid"],
  "failed_message_ids": [],
  "server_messages": [],
  "sync_timestamp": "2026-06-18T00:00:00Z"
}
```

### 7. Get Device Status
**GET** `/devices/{device_id}/status`

Check offline queue status for a device.

**Response:**
```json
{
  "device_id": "device-uuid",
  "offline_message_count": 5,
  "max_offline_messages": 100,
  "queue_enabled": true
}
```

### 8. Clear Offline Messages
**DELETE** `/devices/{device_id}/offline`

Clear all offline messages for a device.

**Response:**
```json
{
  "device_id": "device-uuid",
  "messages_cleared": 5
}
```

## Mobile App Implementation Guidelines

### 1. Connection Handling

#### Online Mode
- Use REST API endpoints for all operations
- Implement WebSocket if supported by the platform
- Use long-polling as fallback for poor network conditions

#### Offline Mode
- Queue messages locally on device
- Store messages with local UUIDs
- Sync when connection is restored using `/sync` endpoint
- Display sync status to user (queued, syncing, synced, failed)

### 2. Message Display

#### Message Types
- **Customer Messages**: Display on right side (blue bubble)
- **Agent Messages**: Display on left side (gray bubble)
- **System Messages**: Display centered with different styling

#### Message Status
- **Sent**: Single checkmark
- **Delivered**: Double checkmark
- **Read**: Double checkmark (blue)
- **Failed**: Red exclamation mark with retry option

### 3. Offline Queueing

#### Queue Management
- Limit to 100 messages (configurable)
- Store in local database (SQLite, Realm, etc.)
- Include timestamp, conversation ID, and attachments
- Display queue count to user

#### Sync Strategy
- Sync on app foreground
- Sync when network becomes available
- Sync on user manual trigger
- Handle sync failures gracefully
- Retry failed messages with exponential backoff

### 4. Push Notifications

#### iOS (APNS)
- Register device token on app launch
- Handle notification permissions
- Display notification with message preview
- Open app to conversation on tap

#### Android (FCM)
- Register device token on app launch
- Handle notification channels
- Display notification with message preview
- Open app to conversation on tap

### 5. Long-Polling Implementation

#### When to Use
- WebSocket not supported
- Poor network conditions
- Battery optimization mode

#### Implementation
- Set timeout to 30 seconds
- Handle timeout gracefully
- Reconnect after timeout
- Cancel on app background

### 6. Error Handling

#### Network Errors
- Display "No connection" indicator
- Queue messages automatically
- Retry failed requests
- Show retry button to user

#### Server Errors
- Display error message to user
- Log error for debugging
- Implement retry logic
- Fallback to offline mode

### 7. UI/UX Requirements

#### Chat Screen
- Message list with timestamps
- Input field with send button
- Attachment button (if supported)
- Typing indicator for agent
- Connection status indicator
- Pull-to-refresh for messages

#### Conversation List
- List of all conversations
- Show last message preview
- Show unread count badge
- Swipe actions (archive, delete)
- Search functionality

#### Loading States
- Skeleton screens for initial load
- Loading indicators for pagination
- Progress indicators for sync
- Spinners for message sending

### 8. Performance Requirements

#### Response Times
- Message send: < 500ms
- Message list load: < 1s
- Long-poll timeout: 30s
- Sync operation: < 5s for 100 messages

#### Memory Usage
- Cache last 100 messages per conversation
- Clear cache on memory warning
- Lazy load older messages
- Compress attachments before upload

#### Battery Optimization
- Use long-polling instead of continuous polling
- Pause sync when app is backgrounded
- Reduce sync frequency on low battery
- Use efficient network libraries

### 9. Security Requirements

#### Data Protection
- Encrypt local message storage
- Use HTTPS for all API calls
- Validate SSL certificates
- Sanitize user input

#### Authentication
- Store JWT token securely (Keychain/Keystore)
- Refresh token before expiry
- Handle token expiry gracefully
- Implement logout functionality

### 10. Platform-Specific Notes

#### iOS
- Use URLSession for network requests
- Implement background fetch for sync
- Use APNS for push notifications
- Handle app lifecycle properly

#### Android
- Use Retrofit/OkHttp for network requests
- Implement WorkManager for sync
- Use FCM for push notifications
- Handle foreground/background states

## Testing Checklist

- [ ] Send message successfully
- [ ] Receive message in real-time
- [ ] Long-polling works on poor network
- [ ] Offline message queuing works
- [ ] Sync restores offline messages
- [ ] Push notifications received
- [ ] Conversation list loads correctly
- [ ] Pagination works for message history
- [ ] Error handling works properly
- [ ] App handles network disconnection
- [ ] App handles reconnection
- [ ] Battery usage is acceptable
- [ ] Memory usage is acceptable

## Troubleshooting

### Common Issues

**Messages not sending**
- Check network connection
- Verify authentication token
- Check server status
- Review offline queue

**Long-polling timing out**
- Increase timeout value
- Check network stability
- Verify server configuration
- Consider WebSocket alternative

**Sync failing**
- Check offline message format
- Verify conversation IDs
- Check server logs
- Retry with smaller batch

**Push notifications not received**
- Verify device token registration
- Check push notification service status
- Verify notification permissions
- Check server push configuration
