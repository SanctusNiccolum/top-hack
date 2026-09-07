import React, { useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { createReport } from '../api';
import { buildRecommendations } from '../utils/recommendations';

const ProfilePage = () => {
  const location = useLocation();
  const [report, setReport] = useState(null);
  const [answers, setAnswers] = useState(null);
  const [user, setUser] = useState({ fullName: 'Иван', age: 18 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const storedAnswers = localStorage.getItem('surveyAnswers');
    const storedUser = localStorage.getItem('user');

    if (storedAnswers) setAnswers(JSON.parse(storedAnswers));
    if (storedUser) setUser(JSON.parse(storedUser));

    if (location.state) {
      if (location.state.answers) setAnswers(location.state.answers);
      if (location.state.user) setUser(location.state.user);
    }

    // Скор и объяснение берём с бэкенда, а не считаем на клиенте.
    // Сумма ежемесячных платежей — ключевой вход формулы (ПДН). Без неё
    // база всегда равна 100 и анкетная ветка вырождается.
    const stored = JSON.parse(localStorage.getItem('surveyAnswers') || '{}');
    const monthlyPayments = Number.parseInt(stored.monthlyPayments, 10) || 0;

    createReport({ monthlyPayments })
      .then(setReport)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [location.state]);

  if (loading || error || !report) {
    return (
      <div style={{ maxWidth: '700px', margin: '2rem auto', padding: '0 1rem', textAlign: 'center' }}>
        <h2 style={{ color: '#07521f' }}>Профиль</h2>
        <p>{loading ? 'Загружаем данные…' : (error || 'Данные не найдены.')}</p>
      </div>
    );
  }

  const survey = answers || {};

  // Рекомендации строятся из посчитанных факторов Telegram и разбора по
  // выписке — см. utils/recommendations.js.
  const recommendations = buildRecommendations(report);

  // Разбивка по веткам: раньше здесь был объект details от клиентского
  // расчёта, которого больше нет.
  const branches = [
    ['Анкета', report.survey_score],
    ['Банковская выписка', report.statement_score]
  ];

  const scorePercent = Math.max(0, Math.min(Number(report.score) || 0, 100));
  const nameParts = (user.fullName || 'Иван').trim().split(/\s+/).filter(Boolean);
  const firstName = nameParts.length > 1 ? nameParts[1] : nameParts[0];

  return (
    <div className="profile-page">
      <div className="profile-layout">
        <aside className="profile-sidebar" aria-label="Навигация профиля">
          {[['↪', 'Выход'], ['▱', 'Папка'], ['◔', 'Оценка'], ['⚙', 'Настройки'], ['👤', 'Профиль пользователя']].map(([icon, label]) => (
            <button key={label} type="button" className="profile-sidebar-button" aria-label={label} title={label}>{icon}</button>
          ))}
        </aside>

        <main className="profile-main">
          <h1 className="profile-title">Оценка благонадежности</h1>
          <section className="profile-score-panel">
            <div className="profile-chart-wrap">
              <div className="profile-chart" style={{ '--score-percent': `${scorePercent * 3.6}deg` }}>
              </div>
            </div>
            <div className="profile-user-summary">
              <h2>{firstName}, {survey.age || 18} лет</h2>
              <strong>{scorePercent}<span>/100</span></strong>
            </div>
          </section>

          <section className="profile-factors">
            <h2>Факторы оценки</h2>
            {branches.map(([label, value]) => (
              <div className="profile-factor" key={label}>
                <span>{label}</span>
                <strong>{value === null ? 'не заполнено' : `${Number(value).toFixed(1)}/100`}</strong>
              </div>
            ))}
            {report.telegram_delta !== null && report.telegram_delta !== undefined && (
              <div className="profile-factor">
                <span>Поправка по Telegram</span>
                <strong>
                  {Number(report.telegram_delta) > 0 ? '+' : ''}
                  {Number(report.telegram_delta).toFixed(1)}
                </strong>
              </div>
            )}
          </section>
        </main>

        <aside className="profile-recommendations">
          <h2><span className="recommendation-star" aria-hidden="true" />Рекомендации от ИИ-ассистента</h2>
          {recommendations.map((recommendation, index) => (
            <article className="profile-recommendation" key={index}>
              <h3>{recommendation.title}</h3>
              <p>{recommendation.text}</p>
            </article>
          ))}
        </aside>
      </div>
    </div>
  );
};

export default ProfilePage;
