'use client';
import { useCallback, useEffect, useState } from 'react';
import { api, ApiError } from '../../lib/api';

export default function Privacy() {
  const [busy, setBusy] = useState('');
  const [message, setMessage] = useState('');

  const eraseMemory = useCallback(async () => {
    if (!confirm('Очистить AI-память во всех диалогах? Отменить это нельзя.')) return;
    setBusy('memory');
    setMessage('');
    try {
      const list = await api<{ id: string; display_name: string | null }[]>('/conversations');
      await Promise.all(list.map((c) => api(`/conversations/${c.id}/memory`, { method: 'DELETE' })));
      setMessage('AI-память очищена.');
    } catch (e) {
      setMessage(e instanceof ApiError ? `Ошибка: ${e.code}` : 'Не удалось очистить память.');
    } finally {
      setBusy('');
    }
  }, []);

  const eraseAccount = useCallback(async () => {
    if (!confirm('Удалить мой аккаунт и все данные безвозвратно? Отменить это нельзя.')) return;
    setBusy('account');
    setMessage('');
    try {
      await api('/account/data', { method: 'DELETE' });
      setMessage('Данные удалены. Перезагрузите приложение — сессия будет недействительна.');
    } catch (e) {
      setMessage(e instanceof ApiError ? `Ошибка: ${e.code}` : 'Не удалось удалить данные.');
    } finally {
      setBusy('');
    }
  }, []);

  return (
    <>
      <h1 className="text-3xl font-bold">Privacy</h1>
      <div className="card mt-5">
        <p>
          AI обрабатывает только чаты, доступные нашему Business Bot и включённые вами для Copilot.
          Пока Copilot выключен, текст сообщений не сохраняется вовсе. Текст хранится максимум 30
          дней, потом удаляется автоматически.
        </p>
        {message && <p className="mt-3 text-green-700">{message}</p>}
        <button
          className="button mt-5 disabled:opacity-50"
          disabled={busy !== ''}
          onClick={eraseMemory}
        >
          {busy === 'memory' ? 'Очищаю…' : 'Очистить AI-память'}
        </button>
        <button
          className="mt-3 w-full rounded-xl border border-red-300 p-3 text-red-600 disabled:opacity-50"
          disabled={busy !== ''}
          onClick={eraseAccount}
        >
          {busy === 'account' ? 'Удаляю…' : 'Удалить мои данные'}
        </button>
      </div>
    </>
  );
}