'use client';
import { useCallback, useEffect, useState } from 'react';
import { api, ApiError } from '../../lib/api';

type Style = {
  tone: string;
  humor_level: number;
  flirt_level: number;
  message_length: string;
  emoji_level: string;
  directness: number;
  custom_instructions: string | null;
};

const DEFAULTS: Style = {
  tone: 'natural',
  humor_level: 5,
  flirt_level: 3,
  message_length: 'short',
  emoji_level: 'low',
  directness: 5,
  custom_instructions: null,
};

export default function Settings() {
  const [style, setStyle] = useState<Style>(DEFAULTS);
  const [status, setStatus] = useState<'loading' | 'saving' | 'saved' | 'error'>('loading');
  const [error, setError] = useState('');

  useEffect(() => {
    api<Style>('/settings/style')
      .then((s) => {
        setStyle({ ...DEFAULTS, ...s });
        setStatus('saved');
      })
      .catch(() => setStatus('error'));
  }, []);

  const update = useCallback(
    async (patch: Partial<Style>) => {
      const next = { ...style, ...patch };
      setStyle(next);
      setStatus('saving');
      try {
        setStyle(await api<Style>('/settings/style', { method: 'PUT', body: JSON.stringify(next) }));
        setStatus('saved');
      } catch (e) {
        setStatus('error');
        setError(e instanceof ApiError ? e.code : String(e));
      }
    },
    [style],
  );

  if (status === 'loading') return <p className="muted">Загрузка…</p>;
  if (status === 'error' && !style)
    return <p className="muted">Не удалось загрузить настройки. Откройте приложение через Telegram.</p>;

  return (
    <>
      <h1 className="text-3xl font-bold">Мой стиль</h1>
      {status === 'saving' && <p className="muted">Сохранение…</p>}
      {status === 'error' && <p className="text-red-600">Ошибка сохранения: {error}</p>}
      <div className="card mt-5 space-y-4">
        <label className="block">
          Основной стиль:
          <select
            className="mt-1 w-full rounded-xl border border-gray-300 p-3"
            value={style.tone}
            onChange={(e) => update({ tone: e.target.value })}
          >
            <option value="natural">Natural</option>
            <option value="playful">Playful</option>
            <option value="romantic">Romantic</option>
            <option value="confident">Confident</option>
            <option value="caring">Caring</option>
          </select>
        </label>
        <label className="block">
          Юмор: {style.humor_level} / 10
          <input
            type="range"
            min={0}
            max={10}
            value={style.humor_level}
            className="mt-1 w-full"
            onChange={(e) => update({ humor_level: Number(e.target.value) })}
          />
        </label>
        <label className="block">
          Флирт: {style.flirt_level} / 10
          <input
            type="range"
            min={0}
            max={10}
            value={style.flirt_level}
            className="mt-1 w-full"
            onChange={(e) => update({ flirt_level: Number(e.target.value) })}
          />
        </label>
        <label className="block">
          Прямолинейность: {style.directness} / 10
          <input
            type="range"
            min={0}
            max={10}
            value={style.directness}
            className="mt-1 w-full"
            onChange={(e) => update({ directness: Number(e.target.value) })}
          />
        </label>
        <label className="block">
          Длина ответа:
          <select
            className="mt-1 w-full rounded-xl border border-gray-300 p-3"
            value={style.message_length}
            onChange={(e) => update({ message_length: e.target.value })}
          >
            <option value="short">Короткие</option>
            <option value="medium">Средние</option>
            <option value="long">Развёрнутые</option>
          </select>
        </label>
        <label className="block">
          Эмодзи:
          <select
            className="mt-1 w-full rounded-xl border border-gray-300 p-3"
            value={style.emoji_level}
            onChange={(e) => update({ emoji_level: e.target.value })}
          >
            <option value="none">Нет</option>
            <option value="low">Немного</option>
            <option value="medium">Средне</option>
            <option value="high">Много</option>
          </select>
        </label>
        <label className="block">
          Своя инструкция (до 500 символов):
          <textarea
            maxLength={500}
            className="mt-1 min-h-24 w-full rounded-xl border border-gray-300 p-3"
            value={style.custom_instructions ?? ''}
            placeholder="Например: избегай фразы «Как дела?»"
            onChange={(e) => update({ custom_instructions: e.target.value || null })}
          />
        </label>
      </div>
    </>
  );
}