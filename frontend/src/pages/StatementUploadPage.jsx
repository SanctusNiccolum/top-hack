import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { uploadStatement } from '../api';

/**
 * Загрузка банковской выписки (PDF за 3 месяца) — основной сценарий кейса.
 * Ответ приходит сразу: бэкенд считает скор синхронно.
 *
 * Маршрут: добавить в App.jsx
 *   <Route path="/statement" element={<StatementUploadPage />} />
 */
const StatementUploadPage = () => {
  const navigate = useNavigate();

  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);

  const handleFile = (event) => {
    setFile(event.target.files?.[0] || null);
    setError('');
    setResult(null);
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!file) return;

    setBusy(true);
    setError('');
    try {
      setResult(await uploadStatement(file));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="statement-page">
      <section className="statement-card" aria-labelledby="statement-title">
        <h1 id="statement-title">Загрузите выписку по карте за 3 месяца</h1>
        <p className="hint">
          Принимаем PDF-выписку из банковского приложения. Файл должен быть
          текстовым, а не сканом — иначе операции не удастся распознать.
        </p>

        <form onSubmit={handleSubmit}>
          <input
            type="file"
            accept="application/pdf,.pdf"
            onChange={handleFile}
            aria-label="PDF-файл выписки"
          />
          <button type="submit" disabled={busy || !file}>
            {busy ? 'Анализируем…' : 'Проанализировать'}
          </button>
        </form>

        {error && <p className="error" role="alert">{error}</p>}

        {result && (
          <div className="statement-result">
            <div className="score-value">
              {Number(result.statement_score).toFixed(0)}<span>/100</span>
            </div>
            <p className="score-caption">оценка по банковской выписке</p>

            {/* ai_comment приходит многострочным — разбиваем, чтобы не
                слиплось в одну строку. */}
            <div className="score-explanation">
              {result.ai_comment.split('\n').map((line, index) => (
                <p key={index}>{line}</p>
              ))}
            </div>

            <button type="button" onClick={() => navigate('/rating')}>
              Перейти к рейтингу
            </button>
          </div>
        )}
      </section>
    </main>
  );
};

export default StatementUploadPage;
