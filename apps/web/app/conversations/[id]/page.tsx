'use client';
import { useEffect, useState } from 'react';
import { api, ApiError } from '../../../lib/api';

type Message = { id: string; direction: 'incoming' | 'outgoing'; text: string | null; created_at: string };
type ConversationDetail = {
  id: string;
  display_name: string | null;
  ai_mode: 'off' | 'copilot';
  messages: Message[];
};
type Suggestion = { id: string; tone: string; text: string };
type Generation = { generation_id: string; options: Suggestion[] };

export default function Conversation({ params }: { params: Promise<{ id: string }> }) {
  const [id, setId] = useState('');
  const [c, setC] = useState<ConversationDetail>();
  const [g, setG] = useState<Generation>();
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    params
      .then((x) => {
        setId(x.id);
        api<ConversationDetail>(`/conversations/${x.id}`)
          .then(setC)
          .catch((e) => setError(e instanceof ApiError ? e.code : 'NETWORK_ERROR'));
      })
      .catch(() => setError('BAD_PATH'));
  }, [params]);

  async function toggleMode() {
    if (!c) return;
    setBusy('mode');
    setError('');
    try {
      const next = c.ai_mode === 'copilot' ? 'off' : 'copilot';
      setC(await api<ConversationDetail>(`/conversations/${id}/ai-mode`, { method: 'PATCH', body: JSON.stringify({ mode: next }) }));
    } catch (e) {
      setError(e instanceof ApiError ? e.code : String(e));
    } finally {
      setBusy('');
    }
  }

  async function suggest() {
    setBusy('suggest');
    setError('');
    try {
      setG(await api<Generation>(`/conversations/${id}/suggestions`, { method: 'POST' }));
    } catch (e) {
      if (e instanceof ApiError) {
        if (e.code === 'QUOTA_EXCEEDED') setError('Лимит генераций на месяц исчерпан.');
        else if (e.code === 'NO_CONTEXT_MESSAGES') setError('Нет сохранённых сообщений: включите Copilot и получите новое сообщение в этом чате.');
        else setError(`Ошибка: ${e.code}`);
      } else setError(String(e));
    } finally {
      setBusy('');
    }
  }

  async function send(optionId: string) {
    setBusy('send');
    setError('');
    try {
      await api(`/conversations/${id}/send`, {
        method: 'POST',
        headers: { 'Idempotency-Key': crypto.randomUUID() },
        body: JSON.stringify({ generation_id: g!.generation_id, option_id: optionId }),
      });
      setG(undefined);
      setError('✓ Отправлено');
    } catch (e) {
      if (e instanceof ApiError) {
        if (e.code === 'SUGGESTION_STALE') setError('Пришло новое сообщение — предложение устарело, сгенерируйте заново.');
        else if (e.code === 'GENERATION_EXPIRED') setError('Предложения устарели (15 минут). Сгенерируйте заново.');
        else setError(`Ошибка: ${e.code}`);
      } else setError(String(e));
    } finally {
      setBusy('');
    }
  }

  if (!c && !error) return <p className="muted">Загрузка…</p>;
  if (error && !c) return <p className="card text-red-600">Не удалось открыть диалог: {error}</p>;

  return (
    <div className="space-y-4">
      <h1 className="text-3xl font-bold">{c!.display_name || 'Диалог'}</h1>
      <button className="button disabled:opacity-50" disabled={busy !== ''} onClick={toggleMode}>
        AI: {c!.ai_mode === 'copilot' ? 'Copilot — включён' : 'Off — выключен'}
      </button>
      <div className="card space-y-2">
        {c!.messages.map((m) => (
          <p key={m.id}>
            <b>{m.direction === 'incoming' ? 'Она/Он' : 'Вы'}:</b>{' '}
            {m.text ?? 'Сообщение скрыто: AI был выключен'}
          </p>
        ))}
        {!c!.messages.length && <p className="muted">Сообщений пока нет.</p>}
      </div>
      {error && <p className={error.startsWith('✓') ? 'text-green-700' : 'text-red-600'}>{error}</p>}
      {c!.ai_mode === 'copilot' && (
        <button className="button disabled:opacity-50" disabled={busy !== ''} onClick={suggest}>
          {busy === 'suggest' ? 'Думаю…' : 'Предложить 3 ответа'}
        </button>
      )}
      {g?.options.map((o) => (
        <section className="card" key={o.id}>
          <b>{o.tone}</b>
          <p className="my-3 whitespace-pre-wrap">{o.text}</p>
          <button className="button disabled:opacity-50" disabled={busy !== ''} onClick={() => send(o.id)}>
            {busy === 'send' ? 'Отправляю…' : 'Отправить'}
          </button>
        </section>
      ))}
    </div>
  );
}