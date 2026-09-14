'use client';

import { useCallback, useState } from 'react';
import { api, ApiError } from '../../lib/api';

type MessageState = { kind: 'success' | 'error'; text: string } | null;

export default function Privacy() {
  const [busy, setBusy] = useState('');
  const [message, setMessage] = useState<MessageState>(null);
  const [deleted, setDeleted] = useState(false);

  const eraseMemory = useCallback(async () => {
    if (!confirm('Очистить AI-память во всех диалогах? Отменить это нельзя.')) return;
    setBusy('memory');
    setMessage(null);
    try {
      await api('/account/memory', { method: 'DELETE' });
      setMessage({ kind: 'success', text: 'AI-память и старые генерации очищены.' });
    } catch (error) {
      setMessage({
        kind: 'error',
        text:
          error instanceof ApiError
            ? `Ошибка: ${error.code}`
            : 'Не удалось очистить AI-память.',
      });
    } finally {
      setBusy('');
    }
  }, []);

  const eraseAccount = useCallback(async () => {
    if (!confirm('Удалить мой аккаунт и все данные безвозвратно? Отменить это нельзя.')) return;
    setBusy('account');
    setMessage(null);
    try {
      await api('/account/data', { method: 'DELETE' });
      setDeleted(true);
      setMessage({
        kind: 'success',
        text: 'Данные удалены, сессия завершена. Повторное открытие создаст новый пустой аккаунт.',
      });
    } catch (error) {
      setMessage({
        kind: 'error',
        text:
          error instanceof ApiError ? `Ошибка: ${error.code}` : 'Не удалось удалить данные.',
      });
    } finally {
      setBusy('');
    }
  }, []);

  return (
    <>
      <h1 className="text-3xl font-bold">Приватность</h1>
      <div className="card mt-5">
        <p>
          AI обрабатывает только чаты, доступные Business Bot и включённые вами для Copilot. Пока
          Copilot выключен, текст новых сообщений не сохраняется. Сохранённый текст удаляется после
          настроенного срока хранения.
        </p>

        {message && (
          <p className={`mt-3 ${message.kind === 'error' ? 'text-red-600' : 'text-green-700'}`}>
            {message.text}
          </p>
        )}

        {!deleted && (
          <>
            <button className="button mt-5 disabled:opacity-50" disabled={busy !== ''} onClick={eraseMemory}>
              {busy === 'memory' ? 'Очищаю…' : 'Очистить AI-память'}
            </button>
            <button className="mt-3 w-full rounded-xl border border-red-300 p-3 text-red-600 disabled:opacity-50" disabled={busy !== ''} onClick={eraseAccount}>
              {busy === 'account' ? 'Удаляю…' : 'Удалить мои данные'}
            </button>
          </>
        )}
      </div>
    </>
  );
}
