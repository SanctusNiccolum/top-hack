import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  grantConsent,
  telegramAnalyze,
  telegramChats,
  telegramSendCode,
  telegramScore,
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
  const [aiResult, setAiResult] = useState(null);
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

          // Разбор закончен — сразу считаем поправку к скору. Отдельной
          // кнопки не делаем: пользователь уже согласился на анализ,
          // лишний шаг только оборвал бы сценарий на полпути.
          if (data.status === 'done') {
            try {
              setAiResult(await telegramScore());
            } catch (err) {
              setAiResult({ status: 'error', explanation_ru: err.message });
            }
          }
        } catch {
          clearInterval(pollTimer.current);
        }
      }, 2000);
    });
  };

  return (
    <main className="telegram-analysis-page telegram-chats-page">
      <section className="telegram-analysis-card telegram-chats-card" aria-labelledby="telegram-analysis-title">
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
            <h1 id="telegram-analysis-title">Выберите чаты для проведения анализа</h1>
            <div className="telegram-chat-list">
              {chats.map((chat) => (
                <label className="telegram-chat-option" key={chat.chat_id}>
                  <input
                    type="checkbox"
                    checked={selected.has(chat.chat_id)}
                    onChange={() => toggleChat(chat.chat_id)}
                  />
                  <span className="telegram-chat-name">{chat.name || chat.chat_id}</span>
                  <span
                    className={`telegram-chat-badge telegram-chat-badge-${
                      chat.type === 'subscription' ? 'investments' : 'personal'
                    }`}
                  >
                    {chat.type === 'subscription' ? 'Подписка' : 'Мои сообщения'}
                  </span>
                </label>
              ))}
            </div>

            <label className="telegram-chats-consent">
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

            <div className="telegram-chats-actions">
              <button
                type="button"
                className="telegram-chats-back"
                onClick={() => navigate('/profile')}
              >
                <span aria-hidden="true">←</span> Вернуться в профиль
              </button>
              <button
                type="button"
                className="telegram-chats-confirm"
                onClick={handleAnalyze}
                disabled={busy || selected.size === 0 || !consentGiven}
              >
                {busy ? 'Запускаем…' : 'Подтвердить'} <span aria-hidden="true">→</span>
              </button>
            </div>

            <p className="telegram-chats-hint" aria-live="polite">
              {selected.size ? `Выбрано чатов: ${selected.size}` : 'Выберите хотя бы один чат'}
            </p>
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
                {progress.status === 'done' && !aiResult && (
                  <p>Анализируем сообщения ИИ…</p>
                )}

                {aiResult && (
                  <div className="telegram-ai-result">
                    {aiResult.status === 'ok' ? (
                      <>
                        <p>
                          <strong>
                            {aiResult.score_delta > 0 ? '+' : ''}
                            {Number(aiResult.score_delta).toFixed(1)} балла
                          </strong>{' '}
                          к оценке
                        </p>
                        <p className="hint">{aiResult.explanation_ru}</p>
                      </>
                    ) : (
                      <p className="hint">
                        Анализ недоступен: {aiResult.explanation_ru}. Оценка по
                        этому источнику не изменена.
                      </p>
                    )}
                  </div>
                )}

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
