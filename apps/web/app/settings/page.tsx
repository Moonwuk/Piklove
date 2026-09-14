'use client';

import { useEffect, useState } from 'react';
import { api, ApiError } from '../../lib/api';

type Style = {
  tone: 'natural' | 'playful' | 'romantic' | 'confident' | 'caring';
  humor_level: number;
  flirt_level: number;
  message_length: 'short' | 'medium' | 'long';
  emoji_level: 'none' | 'low' | 'medium' | 'high';
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
  const [savedStyle, setSavedStyle] = useState<Style>(DEFAULTS);
  const [status, setStatus] = useState<'loading' | 'ready' | 'saving'>('loading');
  const [message, setMessage] = useState('');
  const [isError, setIsError] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);

  useEffect(() => {
    api<Style>('/settings/style')
      .then((loaded) => {
        const normalized = { ...DEFAULTS, ...loaded };
        setStyle(normalized);
        setSavedStyle(normalized);
        setStatus('ready');
      })
      .catch(() => {
        setMessage('Не удалось загрузить настройки. Откройте приложение через Telegram.');
        setIsError(true);
        setLoadFailed(true);
        setStatus('ready');
      });
  }, []);

  const dirty = JSON.stringify(style) !== JSON.stringify(savedStyle);

  function update(patch: Partial<Style>) {
    setStyle((current) => ({ ...current, ...patch }));
    setMessage('');
    setIsError(false);
  }

  async function save() {
    setStatus('saving');
    setMessage('');
    setIsError(false);
    try {
      const saved = await api<Style>('/settings/style', {
        method: 'PUT',
        body: JSON.stringify(style),
      });
      setStyle(saved);
      setSavedStyle(saved);
      setMessage('Настройки сохранены.');
    } catch (error) {
      setMessage(
        error instanceof ApiError ? `Ошибка сохранения: ${error.code}` : 'Не удалось сохранить.',
      );
      setIsError(true);
    } finally {
      setStatus('ready');
    }
  }

  if (status === 'loading') return <p className="muted">Загрузка…</p>;

  return (
    <>
      <h1 className="text-3xl font-bold">Мой стиль</h1>
      <p className="muted mt-1">
        Измените несколько параметров и сохраните их одной кнопкой.
      </p>
      {message && (
        <p className={`mt-3 ${isError ? 'text-red-600' : 'text-green-700'}`}>{message}</p>
      )}

      <div className="card mt-5 space-y-4">
        <label className="block">
          Основной стиль:
          <select
            className="mt-1 w-full rounded-xl border border-gray-300 p-3"
            value={style.tone}
            onChange={(event) => update({ tone: event.target.value as Style['tone'] })}
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
          <input type="range" min={0} max={10} value={style.humor_level} className="mt-1 w-full" onChange={(event) => update({ humor_level: Number(event.target.value) })} />
        </label>
        <label className="block">
          Флирт: {style.flirt_level} / 10
          <input type="range" min={0} max={10} value={style.flirt_level} className="mt-1 w-full" onChange={(event) => update({ flirt_level: Number(event.target.value) })} />
        </label>
        <label className="block">
          Прямолинейность: {style.directness} / 10
          <input type="range" min={0} max={10} value={style.directness} className="mt-1 w-full" onChange={(event) => update({ directness: Number(event.target.value) })} />
        </label>
        <label className="block">
          Длина ответа:
          <select className="mt-1 w-full rounded-xl border border-gray-300 p-3" value={style.message_length} onChange={(event) => update({ message_length: event.target.value as Style['message_length'] })}>
            <option value="short">Короткие</option>
            <option value="medium">Средние</option>
            <option value="long">Развёрнутые</option>
          </select>
        </label>
        <label className="block">
          Эмодзи:
          <select className="mt-1 w-full rounded-xl border border-gray-300 p-3" value={style.emoji_level} onChange={(event) => update({ emoji_level: event.target.value as Style['emoji_level'] })}>
            <option value="none">Нет</option>
            <option value="low">Немного</option>
            <option value="medium">Средне</option>
            <option value="high">Много</option>
          </select>
        </label>
        <label className="block">
          Своя инструкция (до 500 символов):
          <textarea maxLength={500} className="mt-1 min-h-24 w-full rounded-xl border border-gray-300 p-3" value={style.custom_instructions ?? ''} placeholder="Например: избегай фразы «Как дела?»" onChange={(event) => update({ custom_instructions: event.target.value || null })} />
        </label>
        <div className="grid grid-cols-2 gap-2">
          <button className="button disabled:opacity-50" disabled={!dirty || status === 'saving' || loadFailed} onClick={() => void save()}>
            {status === 'saving' ? 'Сохраняю…' : 'Сохранить'}
          </button>
          <button className="rounded-xl border border-gray-300 p-3 disabled:opacity-50" disabled={!dirty || status === 'saving'} onClick={() => { setStyle(savedStyle); setMessage('Изменения отменены.'); setIsError(false); }}>
            Отменить
          </button>
        </div>
      </div>
    </>
  );
}
