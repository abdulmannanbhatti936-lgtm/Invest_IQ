import type {
  ChatHistory,
  SendChatMessageRequest,
  SendChatMessageResponse,
} from '@investiq/shared-types';
import { apiClient } from './client';

export const chatApi = {
  /** Sends one message; the reply is grounded in the user's own data and figure-checked. */
  send: async (body: SendChatMessageRequest): Promise<SendChatMessageResponse> => {
    const { data } = await apiClient.post<SendChatMessageResponse>('/chat/message', body);
    return data;
  },

  /** The user's messages, newest first; `before` pages to older ones. */
  history: async (before?: string | null, limit = 30): Promise<ChatHistory> => {
    const { data } = await apiClient.get<ChatHistory>('/chat/history', {
      params: { limit, ...(before ? { before } : {}) },
    });
    return data;
  },

  clear: async (): Promise<void> => {
    await apiClient.delete('/chat/history');
  },
};
