'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { api, ApiError } from '../lib/api';

declare global {
  interface Window {
    Telegram?: { WebApp: { initData: string; ready(): void; expand(): void } };
  }
}

type Usage = { plan: string; used: number; limit: number };
type Connection = { connected: boolean; can_reply: boolean };

export default function Home() {
  const [connection, setConnection] = useState<Connection | null>(null);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  const bootstrap = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const telegram = window.Telegram?.WebApp;
      if (!telegram?.initData) {
        setConnection({ connected: false, can_reply: false });
        setUsage(null);
        setError('OPEN_IN_TELEGRAM');
        return;
      }
      telegram.ready();
      telegram.expand();
      await api('/auth/telegram', {
        method: 'POST',
        body: JSON.stringify({ init_data: telegram.initData }),
      });
      const [nextConnection, nextUsage] = await Promise.all([
        api<Connection>('/telegram/connection'),
        api<Usage>('/billing/usage'),
      ]);
      setConnection(nextConnection);
      setUsage(nextUsage);
    } catch (bootstrapError) {
      setConnection({ connected: false, can_reply: false });
      setUsage(null);
      setError(bootstrapError instanceof ApiError ? bootstrapError.code : 'NETWORK_ERROR');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void bootstrap();
  }, [bootstrap]);

  return (
    <div className="space-y-4">
      <h1 className="text-3xl font-bold">PikLove AI Copilot</h1>

      {error === 'OPEN_IN_TELEGRAM' && (
        <section className="card text-amber-700">
          Откройте Mini App из Telegram. В обычном браузере Telegram не передаёт данные для входа.
        </section>
      )}
      {error && error !== 'OPEN_IN_TELEGRAM' && (
        <section className="card text-red-600">
          Не удалось запустить приложение: {error}
          <button className="mt-3 w-full rounded-xl border border-red-300 p-3" onClick={bootstrap}>
            Повторить
          </button>
        </section>
      )}

      <section className="card">
        <p className="font-semibold">Telegram Business</p>
        <p className={connection?.connected ? 'text-green-600' : 'muted'}>
          {loading
            ? 'Проверяю подключение…'
            : connection?.connected
              ? connection.can_reply
                ? '● Подключён, можно отвечать'
                : '● Подключён, но право отвечать выключено в Telegram'
              : '○ Не подключён'}
        </p>
      </section>

      {!loading && connection && !connection.connected && error !== 'OPEN_IN_TELEGRAM' && (
        <section className="card">
          <h2 className="font-bold">Подключите Telegram Business</h2>
          <p className="muted mt-2">
            PikLove работает только с чатами, переданными официальному Business Bot. Пароль и код
            Telegram не требуются.
          </p>
        </section>
      )}

      <section className="card">
        <p>
          План: <b>{usage ? usage.plan.toUpperCase() : '—'}</b>
        </p>
        <p>AI usage: {usage ? `${usage.used} / ${usage.limit}` : '—'}</p>
        {usage && usage.used >= usage.limit && (
          <p className="mt-2 text-amber-600">
            Лимит генераций на этот месяц исчерпан. Он обновится первого числа.
          </p>
        )}
      </section>

      <Link className="button text-center" href="/conversations">
        Диалоги
      </Link>
      <div className="grid grid-cols-2 gap-3">
        <Link className="card text-center" href="/settings">
          Настройки
        </Link>
        <Link className="card text-center" href="/privacy">
          Приватность
        </Link>
      </div>
    </div>
  );
}
