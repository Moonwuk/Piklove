'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { api, ApiError } from '../../lib/api';

type Conversation = {
  id: string;
  display_name: string | null;
  username: string | null;
  ai_mode: 'off' | 'copilot';
  last_message_at: string | null;
};

export default function Conversations() {
  const [conversations, setConversations] = useState<Conversation[] | null>(null);
  const [error, setError] = useState('');
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async (silent = false) => {
    if (!silent) setRefreshing(true);
    try {
      setConversations(await api<Conversation[]>('/conversations'));
      setError('');
    } catch (loadError) {
      if (!silent) {
        setError(loadError instanceof ApiError ? loadError.code : 'NETWORK_ERROR');
        setConversations([]);
      }
    } finally {
      if (!silent) setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(true), 10000);
    return () => window.clearInterval(timer);
  }, [load]);

  return (
    <>
      <div className="mb-5 flex items-center justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold">Диалоги</h1>
          <p className="muted text-sm">Список обновляется автоматически.</p>
        </div>
        <button
          className="rounded-xl border border-gray-300 px-3 py-2 text-sm disabled:opacity-50"
          disabled={refreshing}
          onClick={() => void load()}
        >
          {refreshing ? 'Обновляю…' : 'Обновить'}
        </button>
      </div>

      {error && <div className="card text-red-600">Не удалось загрузить: {error}</div>}
      <div className="space-y-3">
        {(conversations ?? []).map((conversation) => (
          <Link
            key={conversation.id}
            href={`/conversations/${conversation.id}`}
            className="card block"
          >
            <b>{conversation.display_name || conversation.username || 'Telegram chat'}</b>
            <p className="muted">
              AI: {conversation.ai_mode === 'copilot' ? 'Copilot' : 'Off'}
            </p>
            {conversation.last_message_at && (
              <p className="muted text-xs">
                Последнее сообщение:{' '}
                {new Date(conversation.last_message_at).toLocaleString('ru-RU')}
              </p>
            )}
          </Link>
        ))}
        {conversations && !conversations.length && !error && (
          <div className="card muted">
            Здесь появятся только чаты, переданные подключённому Business Bot.
          </div>
        )}
      </div>
    </>
  );
}
