import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';

const TelegramAnalysisPage = () => {
  const navigate = useNavigate();
  const [telegramId, setTelegramId] = useState('');

  const handleSubmit = (event) => {
    event.preventDefault();
    const normalizedId = telegramId.trim();
    if (!normalizedId) return;
    localStorage.setItem('telegramAnalysisId', normalizedId);
    navigate('/profile');
  };

  return (
    <main className="telegram-analysis-page">
      <section className="telegram-analysis-card" aria-labelledby="telegram-analysis-title">
        <h1 id="telegram-analysis-title">Введите Ваш номер телефона или юзернейм в Telegram</h1>
        <form onSubmit={handleSubmit}>
          <input
            type="text"
            value={telegramId}
            onChange={(event) => setTelegramId(event.target.value)}
            aria-label="Номер телефона или юзернейм в Telegram"
            autoComplete="off"
            autoFocus
          />
          <button type="submit" disabled={!telegramId.trim()}>Далее <span aria-hidden="true">-&gt;</span></button>
        </form>
      </section>
    </main>
  );
};

export default TelegramAnalysisPage;
