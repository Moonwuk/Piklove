'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { api, ApiError } from '../lib/api';

declare global {
  interface Window {
    Telegram?: { WebApp: { initData: string; ready(): void; expand(): void } };
  }
}

type Usage = { plan: string; used: number; limit: number };
type Connection = { connected: boolean; can_reply: boolean };

export default function Home() {
  const [connected, setConnected] = useState<Connection | null>(null);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [authError, setAuthError] = useState('');

  useEffect(() => {
    (async () => {
      const tg = window.Telegram?.WebApp;
      tg?.ready();
      tg?.expand();
      try {
        if (tg?.initData) {
          await api('/auth/telegram', {
            method: 'POST',
            body: JSON.stringify({ init_data: tg.initData }),
          });
        }
        setConnected(await api<Connection>('/telegram/connection'));
        setUsage(await api<Usage>('/billing/usage'));
      } catch (e) {
        setConnected({ connected: false, can_reply: false });
        setAuthError(e instanceof ApiError ? e.code : 'NETWORK_ERROR');
      }
    })();
  }, []);

  return (
    <div className="space-y-4">
      <h1 className="text-3xl font-bold">AI Copilot</h1>
      <section className="card">
        <p className="font-semibold">Telegram Business</p>
        <p className={connected?.connected ? 'text-green-600' : 'muted'}>
          {connected
            ? connected.connected
              ? connected.can_reply
                ? '● Подключён, можно отвечать'
                : '● Подключён, но реплаи выключены в настройках Telegram'
              : '○ Не подключён'
            : `○ Статус неизвестен (${authError})`}
        </p>
      </section>
      {connected && !connected.connected && (
        <section className="card">
          <h2 className="font-bold">Подключите Telegram Business</h2>
          <p className="muted mt-2">
            AI работает только с чатами, доступными Business Bot и включёнными вами для Copilot. Мы
            не просим пароль или код Telegram.
          </p>
        </section>
      )}
      <section className="card">
        <p>
          План: <b>{usage ? usage.plan.toUpperCase() : '…'}</b>
        </p>
        <p>
          AI usage: {usage ? `${usage.used} / ${usage.limit}` : '…'}
        </p>
        {usage && usage.used >= usage.limit && (
          <p className="mt-2 text-amber-600">
            Лимит генераций на этот месяц исчерпан. Он обновится 1-го числа.
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
          Privacy
        </Link>
      </div>
    </div>
  );
}