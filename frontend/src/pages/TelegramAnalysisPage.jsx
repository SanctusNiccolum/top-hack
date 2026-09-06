import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  grantConsent,
  telegramAnalyze,
  telegramChats,
  telegramSendCode,
  telegramStatus,
  telegramSubmitCode,
  telegramSubmitPassword
} from '../api';

/**
 * Подключение Telegram: телефон -> код -> (пароль 2FA) -> выбор чатов -> разбор.
 *
 * Вход только по номеру телефона: войти по @юзернейму нельзя, это
 * ограничение протокола Telegram, а не бэкенда.
 */

const STEPS = {
  PHONE: 'phone',
  CODE: 'code',
  PASSWORD: 'password',
  CHATS: 'chats',
  PROGRESS: 'progress'
};

const TelegramAnalysisPage = () => {
  const navigate = useNavigate();

  const [step, setStep] = useState(STEPS.PHONE);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const [phone, setPhone] = useState('');
  const [code, setCode] = useState('');
  const [password, setPassword] = useState('');

  const [loginId, setLoginId] = useState('');
  const [sessionString, setSessionString] = useState('');

  const [chats, setChats] = useState([]);
  const [selected, setSelected] = useState(() => new Set());

  const [consentGiven, setConsentGiven] = useState(false);
  const [progress, setProgress] = useState(null);
  const pollTimer = useRef(null);

  useEffect(() => () => clearInterval(pollTimer.current), []);

  const run = async (action) => {
    setBusy(true);
    setError('');
    try {
      await action();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const loadChats = async (session) => {
    const data = await telegramChats(session);
    setChats(data.chats);
    setStep(STEPS.CHATS);
  };

  const handlePhone = (event) => {
    event.preventDefault();
    run(async () => {
      const data = await telegramSendCode(phone.trim());
      setLoginId(data.login_id);
      setStep(STEPS.CODE);
    });
  };

  const handleCode = (event) => {
    event.preventDefault();
    run(async () => {
      const data = await telegramSubmitCode(loginId, code.trim());
      if (data.status === 'need_password') {
        setStep(STEPS.PASSWORD);
        return;
      }
      setSessionString(data.session_string);
      await loadChats(data.session_string);
    });
  };

  const handlePassword = (event) => {
    event.preventDefault();
    run(async () => {
      const data = await telegramSubmitPassword(loginId, password);
      setSessionString(data.session_string);
      await loadChats(data.session_string);
    });
  };

  const toggleChat = (chatId) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(chatId)) next.delete(chatId);
      else next.add(chatId);
      return next;
    });
  };

  const handleAnalyze = () => {
    run(async () => {
      // Бэкенд не запустит разбор без записи согласия — фиксируем его
      // ровно в момент, когда пользователь нажал «Анализировать».
      await grantConsent('telegram_analysis', 'v1');
      await telegramAnalyze(sessionString, [...selected]);
      setStep(STEPS.PROGRESS);

      // Разбор идёт в фоне, поэтому опрашиваем статус, пока не завершится.
      pollTimer.current = setInterval(async () => {
        try {
          const data = await telegramStatus();
          setProgress(data);
          if (data.status === 'done' || data.status === 'failed') {
            clearInterval(pollTimer.current);
          }
        } catch {
          clearInterval(pollTimer.current);
        }
      }, 2000);
    });
  };

  return (
    <main className="telegram-analysis-page">
      <section className="telegram-analysis-card" aria-labelledby="telegram-analysis-title">
        {step === STEPS.PHONE && (
          <>
            <h1 id="telegram-analysis-title">Введите номер телефона Telegram</h1>
            <form onSubmit={handlePhone}>
              <input
                type="tel"
                value={phone}
                onChange={(event) => setPhone(event.target.value)}
                placeholder="+79991234567"
                aria-label="Номер телефона в Telegram"
                autoComplete="tel"
                autoFocus
              />
              <button type="submit" disabled={busy || !phone.trim()}>
                {busy ? 'Отправляем…' : 'Получить код'}
              </button>
            </form>
            <p className="hint">Мы отправим код подтверждения в Ваш Telegram.</p>
          </>
        )}

        {step === STEPS.CODE && (
          <>
            <h1 id="telegram-analysis-title">Код из Telegram</h1>
            <form onSubmit={handleCode}>
              <input
                type="text"
                inputMode="numeric"
                value={code}
                onChange={(event) => setCode(event.target.value)}
                aria-label="Код подтверждения"
                autoComplete="one-time-code"
                autoFocus
              />
              <button type="submit" disabled={busy || !code.trim()}>
                {busy ? 'Проверяем…' : 'Подтвердить'}
              </button>
            </form>
          </>
        )}

        {step === STEPS.PASSWORD && (
          <>
            <h1 id="telegram-analysis-title">Пароль двухфакторной защиты</h1>
            <form onSubmit={handlePassword}>
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                aria-label="Пароль двухфакторной защиты Telegram"
                autoComplete="current-password"
                autoFocus
              />
              <button type="submit" disabled={busy || !password}>
                {busy ? 'Проверяем…' : 'Войти'}
              </button>
            </form>
          </>
        )}

        {step === STEPS.CHATS && (
          <>
            <h1 id="telegram-analysis-title">Выберите, что анализировать</h1>
            <p className="hint">
              Анализируются только выбранные Вами чаты. Ваши сообщения очищаются
              от телефонов, почт и упоминаний перед сохранением.
            </p>
            <ul className="chat-list">
              {chats.map((chat) => (
                <li key={chat.chat_id}>
                  <label>
                    <input
                      type="checkbox"
                      checked={selected.has(chat.chat_id)}
                      onChange={() => toggleChat(chat.chat_id)}
                    />
                    <span className="chat-name">{chat.name || chat.chat_id}</span>
                    <span className="chat-type">
                      {chat.type === 'subscription' ? 'подписка' : 'мои сообщения'}
                    </span>
                  </label>
                </li>
              ))}
            </ul>
            <label className="consent-check">
              <input
                type="checkbox"
                checked={consentGiven}
                onChange={(event) => setConsentGiven(event.target.checked)}
              />
              <span>
                Я согласен на обработку данных выбранных чатов для оценки
                платёжеспособности и понимаю, что могу отозвать согласие.
              </span>
            </label>
            <button
              type="button"
              onClick={handleAnalyze}
              disabled={busy || selected.size === 0 || !consentGiven}
            >
              {busy ? 'Запускаем…' : `Анализировать (${selected.size})`}
            </button>
          </>
        )}

        {step === STEPS.PROGRESS && (
          <>
            <h1 id="telegram-analysis-title">Анализируем</h1>
            {!progress && <p>Запускаем разбор…</p>}
            {progress && (
              <>
                <p>
                  {progress.status === 'done' && 'Готово!'}
                  {progress.status === 'in_progress' && 'Идёт разбор чатов…'}
                  {progress.status === 'failed' && 'Не удалось разобрать чаты.'}
                  {progress.status === 'not_started' && 'Ожидаем начала…'}
                </p>
                <p className="hint">
                  Сообщений собрано: {progress.messages_collected} · Подписок: {progress.subscriptions_collected}
                </p>
                {progress.status === 'done' && (
                  <button type="button" onClick={() => navigate('/rating')}>
                    Перейти к рейтингу
                  </button>
                )}
              </>
            )}
          </>
        )}

        {error && <p className="error" role="alert">{error}</p>}
      </section>
    </main>
  );
};

export default TelegramAnalysisPage;
