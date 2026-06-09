const STORAGE_KEYS = {
  anonymousUserId: "ai_support_anonymous_user_id",
  sessionId: "ai_support_session_id",
  conversationId: "ai_support_conversation_id",
  lastConversationId: "ai_support_last_conversation_id",
  lastActiveAt: "ai_support_last_active_at",
};

export function getOrCreateAnonymousUserId() {
  let id = localStorage.getItem(STORAGE_KEYS.anonymousUserId);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(STORAGE_KEYS.anonymousUserId, id);
  }
  return id;
}

export function getStoredSession() {
  return {
    anonymousUserId: localStorage.getItem(STORAGE_KEYS.anonymousUserId),
    sessionId: localStorage.getItem(STORAGE_KEYS.sessionId),
    conversationId: localStorage.getItem(STORAGE_KEYS.conversationId),
    lastConversationId: localStorage.getItem(STORAGE_KEYS.lastConversationId),
    lastActiveAt: localStorage.getItem(STORAGE_KEYS.lastActiveAt),
  };
}

export function saveSession({ anonymousUserId, sessionId, conversationId, lastActiveAt }) {
  localStorage.setItem(STORAGE_KEYS.anonymousUserId, anonymousUserId);
  localStorage.setItem(STORAGE_KEYS.sessionId, sessionId);
  localStorage.setItem(STORAGE_KEYS.conversationId, conversationId);
  localStorage.setItem(STORAGE_KEYS.lastConversationId, conversationId);
  if (lastActiveAt) {
    localStorage.setItem(STORAGE_KEYS.lastActiveAt, lastActiveAt);
  }
}

export function saveLastConversation(conversationId, lastActiveAt) {
  localStorage.setItem(STORAGE_KEYS.lastConversationId, conversationId);
  if (lastActiveAt) {
    localStorage.setItem(STORAGE_KEYS.lastActiveAt, lastActiveAt);
  }
}

export function clearSession() {
  localStorage.removeItem(STORAGE_KEYS.sessionId);
  localStorage.removeItem(STORAGE_KEYS.conversationId);
}
