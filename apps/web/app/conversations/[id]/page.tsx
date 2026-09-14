'use client';

import { useCallback, useEffect, useState } from 'react';
import { api, ApiError } from '../../../lib/api';

type Message = {
  id: string;
  direction: 'incoming' | 'outgoing';
  text: string | null;
  created_at: string;
};

type ConversationDetail = {
  id: string;
  display_name: string | null;
  username: string | null;
  ai_mode: 'off' | 'copilot';
  last_message_at: string | null;
  messages: Message[];
};

type ConversationSummary = Omit<ConversationDetail, 'messages'>;
type Suggestion = { id: string; tone: string; text: string };
type Generation = { generation_id: string; options: Suggestion[] };
type SendResult = {
  status: 'pending' | 'sent' | 'failed' | 'unknown';
  telegram_message_id: number | null;
};
type Notice = { kind: 'error' | 'success' | 'info'; text: string } | null;
type RetryState = { fingerprint: string; key: string } | null;

function apiMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return 'Ошибка сети. Проверьте соединение и повторите.';
  const messages: Record<string, string> = {
    QUOTA_EXCEEDED: 'Лимит генераций на месяц исчерпан.',
    NO_CONTEXT_MESSAGES:
      'Нет сохранённых сообщений. Включите Copilot и получите новое сообщение в этом чате.',
    AI_PROVIDER_NOT_CONFIGURED:
      'AI не настроен на сервере: проверьте ключ и имена моделей.',
    AI_PROVIDER_UNAVAILABLE:
      'AI-провайдер сейчас недоступен. Попробуйте ещё раз чуть позже.',
    SUGGESTION_STALE:
      'Пришло новое сообщение — предложения устарели. Сгенерируйте новые.',
    GENERATION_EXPIRED: 'Предложения устарели. Сгенерируйте новые.',
    GENERATION_ALREADY_SENT: 'Этот набор предложений уже был использован.',
    TELEGRAM_SEND_UNKNOWN:
      'Telegram не подтвердил результат. Повторите ту же отправку: дубликат не будет создан.',
    BUSINESS_CONNECTION_INACTIVE:
      'Business Bot отключён или больше не имеет права отвечать.',
    IDEMPOTENCY_KEY_REUSED: 'Повторная отправка не совпала с исходным запросом.',
  };
  return messages[error.code] ?? `Ошибка: ${error.code}`;
}

export default function Conversation({ params }: { params: Promise<{ id: string }> }) {
  const [id, setId] = useState('');
  const [conversation, setConversation] = useState<ConversationDetail>();
  const [generation, setGeneration] = useState<Generation>();
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState('');
  const [notice, setNotice] = useState<Notice>(null);
  const [retry, setRetry] = useState<RetryState>(null);

  const loadConversation = useCallback(async (conversationId: string, silent = false) => {
    try {
      const next = await api<ConversationDetail>(`/conversations/${conversationId}`);
      setConversation(next);
      if (!silent) setNotice(null);
    } catch (error) {
      if (!silent) setNotice({ kind: 'error', text: apiMessage(error) });
    }
  }, []);

  useEffect(() => {
    let active = true;
    let timer: number | undefined;
    params
      .then(({ id: conversationId }) => {
        if (!active) return;
        setId(conversationId);
        void loadConversation(conversationId);
        timer = window.setInterval(() => {
          void loadConversation(conversationId, true);
        }, 5000);
      })
      .catch(() => setNotice({ kind: 'error', text: 'Некорректная ссылка на диалог.' }));
    return () => {
      active = false;
      if (timer) window.clearInterval(timer);
    };
  }, [loadConversation, params]);

  async function toggleMode() {
    if (!conversation) return;
    setBusy('mode');
    setNotice(null);
    try {
      const mode = conversation.ai_mode === 'copilot' ? 'off' : 'copilot';
      const updated = await api<ConversationSummary>(`/conversations/${id}/ai-mode`, {
        method: 'PATCH',
        body: JSON.stringify({ mode }),
      });
      setConversation((current) => (current ? { ...current, ...updated } : current));
      setGeneration(undefined);
      setDraft('');
      setRetry(null);
      setNotice({
        kind: 'info',
        text:
          mode === 'copilot'
            ? 'Copilot включён. Для приватности AI увидит только новые сообщения.'
            : 'Copilot выключен. Текст новых сообщений сохраняться не будет.',
      });
    } catch (error) {
      setNotice({ kind: 'error', text: apiMessage(error) });
    } finally {
      setBusy('');
    }
  }

  async function suggest() {
    setBusy('suggest');
    setNotice(null);
    try {
      const result = await api<Generation>(`/conversations/${id}/suggestions`, {
        method: 'POST',
      });
      setGeneration(result);
      setDraft('');
      setRetry(null);
    } catch (error) {
      setNotice({ kind: 'error', text: apiMessage(error) });
    } finally {
      setBusy('');
    }
  }

  async function performSend(
    endpoint: 'send' | 'send-custom',
    body: Record<string, string>,
    fingerprint: string,
  ) {
    const key = retry?.fingerprint === fingerprint ? retry.key : crypto.randomUUID();
    setRetry({ fingerprint, key });
    setBusy('send');
    setNotice(null);
    try {
      const result = await api<SendResult>(`/conversations/${id}/${endpoint}`, {
        method: 'POST',
        headers: { 'Idempotency-Key': key },
        body: JSON.stringify(body),
      });
      if (result.status === 'sent') {
        setGeneration(undefined);
        setDraft('');
        setRetry(null);
        setNotice({ kind: 'success', text: 'Сообщение отправлено.' });
        await loadConversation(id, true);
      } else if (result.status === 'pending') {
        setNotice({
          kind: 'info',
          text: 'Отправка уже выполняется. Нажмите ту же кнопку ещё раз, чтобы проверить статус.',
        });
      } else if (result.status === 'unknown') {
        setNotice({
          kind: 'error',
          text: 'Результат отправки пока неизвестен. Повторите ту же отправку для проверки статуса.',
        });
      } else {
        setNotice({ kind: 'error', text: 'Telegram отклонил отправку.' });
      }
    } catch (error) {
      setNotice({ kind: 'error', text: apiMessage(error) });
      if (error instanceof ApiError && error.status < 500) setRetry(null);
    } finally {
      setBusy('');
    }
  }

  async function sendOption(option: Suggestion) {
    if (!generation) return;
    await performSend(
      'send',
      { generation_id: generation.generation_id, option_id: option.id },
      `option:${generation.generation_id}:${option.id}`,
    );
  }

  async function sendCustom() {
    if (!generation || !draft.trim()) return;
    const text = draft.trim();
    await performSend(
      'send-custom',
      { generation_id: generation.generation_id, text },
      `custom:${generation.generation_id}:${text}`,
    );
  }

  if (!conversation && !notice) return <p className="muted">Загрузка…</p>;
  if (!conversation)
    return <p className="card text-red-600">Не удалось открыть диалог: {notice?.text}</p>;

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold">
            {conversation.display_name || conversation.username || 'Диалог'}
          </h1>
          <p className="muted text-sm">Сообщения обновляются автоматически.</p>
        </div>
        <button
          className="rounded-xl border border-gray-300 px-3 py-2 text-sm disabled:opacity-50"
          disabled={busy !== ''}
          onClick={() => void loadConversation(id)}
        >
          Обновить
        </button>
      </div>

      <button className="button disabled:opacity-50" disabled={busy !== ''} onClick={toggleMode}>
        AI: {conversation.ai_mode === 'copilot' ? 'Copilot — включён' : 'Off — выключен'}
      </button>

      <div className="card max-h-[45vh] space-y-2 overflow-y-auto">
        {conversation.messages.map((message) => (
          <p key={message.id}>
            <b>{message.direction === 'incoming' ? 'Собеседник' : 'Вы'}:</b>{' '}
            {message.text ?? 'Текст не сохранялся: Copilot был выключен'}
          </p>
        ))}
        {!conversation.messages.length && <p className="muted">Сообщений пока нет.</p>}
      </div>

      {notice && (
        <p
          className={
            notice.kind === 'success'
              ? 'text-green-700'
              : notice.kind === 'error'
                ? 'text-red-600'
                : 'muted'
          }
        >
          {notice.text}
        </p>
      )}

      {conversation.ai_mode === 'copilot' && (
        <button className="button disabled:opacity-50" disabled={busy !== ''} onClick={suggest}>
          {busy === 'suggest' ? 'Готовлю ответы…' : 'Предложить 3 ответа'}
        </button>
      )}

      {generation?.options.map((option) => (
        <section className="card" key={option.id}>
          <b>{option.tone}</b>
          <p className="my-3 whitespace-pre-wrap">{option.text}</p>
          <div className="grid grid-cols-2 gap-2">
            <button
              className="button disabled:opacity-50"
              disabled={busy !== ''}
              onClick={() => void sendOption(option)}
            >
              {busy === 'send' ? 'Отправляю…' : 'Отправить'}
            </button>
            <button
              className="rounded-xl border border-gray-300 p-3 disabled:opacity-50"
              disabled={busy !== ''}
              onClick={() => {
                setDraft(option.text);
                setRetry(null);
              }}
            >
              Изменить
            </button>
          </div>
        </section>
      ))}

      {generation && draft !== '' && (
        <section className="card space-y-3">
          <label className="font-semibold" htmlFor="custom-reply">
            Отредактированный ответ
          </label>
          <textarea
            id="custom-reply"
            maxLength={4096}
            className="min-h-28 w-full rounded-xl border border-gray-300 p-3"
            value={draft}
            onChange={(event) => {
              setDraft(event.target.value);
              setRetry(null);
            }}
          />
          <button
            className="button disabled:opacity-50"
            disabled={busy !== '' || !draft.trim()}
            onClick={() => void sendCustom()}
          >
            {busy === 'send' ? 'Отправляю…' : 'Отправить отредактированный'}
          </button>
        </section>
      )}
    </div>
  );
}
