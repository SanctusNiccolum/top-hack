/**
 * Клиент бэкенда.
 *
 * Положить в src/api.js — все страницы ходят в API только через него,
 * чтобы адрес бэкенда и работа с токеном лежали в одном месте.
 *
 * Адрес берётся из VITE_API_URL (файл .env), иначе локальный docker-compose,
 * где backend проброшен на 8001.
 */

const BASE_URL = import.meta.env?.VITE_API_URL || 'http://localhost:8001';

const TOKEN_KEY = 'sessionToken';

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

/** Ошибка запроса с человекочитаемым текстом из поля detail бэкенда. */
export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

async function request(path, { method = 'GET', body, auth = true, isForm = false } = {}) {
  const headers = {};

  if (auth) {
    const token = getToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  }

  if (!isForm && body !== undefined) {
    headers['Content-Type'] = 'application/json';
  }

  const response = await fetch(`${BASE_URL}${path}`, {
    method,
    headers,
    body: isForm ? body : (body !== undefined ? JSON.stringify(body) : undefined)
  });

  const text = await response.text();
  const data = text ? JSON.parse(text) : null;

  if (!response.ok) {
    // FastAPI кладёт текст ошибки в detail; при ошибке валидации это
    // массив объектов, поэтому разбираем оба варианта.
    const detail = data?.detail;
    const message = Array.isArray(detail)
      ? detail.map((item) => item.msg).join('; ')
      : (detail || `Ошибка запроса (${response.status})`);
    throw new ApiError(message, response.status);
  }

  return data;
}

/* ---------------------------------------------------------------- Аккаунт */

export async function register(phoneNumber, password) {
  const data = await request('/account', {
    method: 'POST',
    auth: false,
    body: { phone_number: phoneNumber, password }
  });
  setToken(data.session_token);
  return data;
}

export async function login(phoneNumber, password) {
  const data = await request('/auth/login', {
    method: 'POST',
    auth: false,
    body: { phone_number: phoneNumber, password }
  });
  setToken(data.session_token);
  return data;
}

export function getAccount() {
  return request('/account');
}

/** Частичное обновление анкеты: шлём только заполненные поля. */
export function updateAccount(fields) {
  return request('/account', { method: 'PUT', body: fields });
}

/** Отмечает анкету завершённой — без этого /report вернёт ошибку. */
export function completeAccount() {
  return request('/account/complete', { method: 'POST' });
}

/* ----------------------------------------------------------------- Отчёт */

/**
 * Считает скор. Возвращает итог и разбивку по веткам:
 * survey_score / statement_score / telegram_score (null = ветка не считалась).
 */
export function createReport({ monthlyPayments = 0, npdCertificateAttached = false } = {}) {
  return request('/report', {
    method: 'POST',
    body: {
      monthly_payments: monthlyPayments,
      npd_certificate_attached: npdCertificateAttached
    }
  });
}

/* --------------------------------------------------------- Выписка (PDF) */

/**
 * Загружает PDF-выписку и сразу возвращает скор по ней.
 * Запрос синхронный: расчёт занимает секунды.
 */
export function uploadStatement(file) {
  const form = new FormData();
  form.append('file', file);
  return request('/statement/upload', { method: 'POST', body: form, isForm: true });
}

/* -------------------------------------------------------------- Согласия */

/**
 * Фиксирует согласие пользователя. Без согласия типа 'telegram_analysis'
 * бэкенд не запустит разбор Telegram и ответит 403.
 * Типы: 'telegram_analysis' | 'bank_statement' | 'personal_data'.
 */
export function grantConsent(consentType, documentVersion = null) {
  return request('/consent', {
    method: 'POST',
    body: { consent_type: consentType, document_version: documentVersion }
  });
}

export function listConsents() {
  return request('/consent');
}

/** Отзывает согласие: запись сохраняется, проставляется revoked_at. */
export function revokeConsent(consentType) {
  return request(`/consent/${consentType}`, { method: 'DELETE' });
}

/* -------------------------------------------------------------- Telegram */

/** Шаг 1: отправляет код в Telegram. Возвращает { login_id }. */
export function telegramSendCode(phoneNumber) {
  return request('/telegram/login/phone', {
    method: 'POST',
    body: { phone_number: phoneNumber }
  });
}

/**
 * Шаг 2: подтверждает код.
 * Возвращает { status: 'ok' | 'need_password', session_string, telegram_user_id }.
 */
export function telegramSubmitCode(loginId, code) {
  return request('/telegram/login/code', {
    method: 'POST',
    body: { login_id: loginId, code }
  });
}

/** Шаг 3 (только если status был 'need_password'): пароль двухфакторки. */
export function telegramSubmitPassword(loginId, password) {
  return request('/telegram/login/password', {
    method: 'POST',
    body: { login_id: loginId, password }
  });
}

/** Список диалогов: { chats: [{ chat_id, name, username, type }] }. */
export function telegramChats(sessionString) {
  return request('/telegram/chats', {
    method: 'POST',
    body: { session_string: sessionString }
  });
}

/**
 * Запускает разбор выбранных чатов. Отвечает сразу (202), сам разбор идёт
 * в фоне — прогресс смотреть через telegramStatus().
 *
 * Важно: session_string одноразовый — парсер отзывает сессию в конце,
 * поэтому после этого вызова придётся логиниться заново.
 */
export function telegramAnalyze(sessionString, chatIds) {
  return request('/telegram/analyze', {
    method: 'POST',
    body: { session_string: sessionString, chat_ids: chatIds }
  });
}

/**
 * Прогресс разбора:
 * { status: 'not_started' | 'in_progress' | 'done' | 'failed',
 *   chats: [...], messages_collected, subscriptions_collected }
 */
export function telegramStatus() {
  return request('/telegram/status');
}
