'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
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

  useEffect(() => {
    api<Conversation[]>('/conversations')
      .then(setConversations)
      .catch((e) => {
        setError(e instanceof ApiError ? e.code : 'NETWORK_ERROR');
        setConversations([]);
      });
  }, []);

  return (
    <>
      <h1 className="mb-5 text-3xl font-bold">Диалоги</h1>
      {error && <div className="card text-red-600">Не удалось загрузить: {error}</div>}
      <div className="space-y-3">
        {(conversations ?? []).map((c) => (
          <Link
            key={c.id}
            href={`/conversations/${c.id}`}
            className="card block"
          >
            <b>{c.display_name || c.username || 'Telegram chat'}</b>
            <p className="muted">AI: {c.ai_mode === 'copilot' ? 'Copilot' : 'Off'}</p>
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