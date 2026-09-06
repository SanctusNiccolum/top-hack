import React, { useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { generateRecommendations } from '../utils/generateRecommendations';

const ProfilePage = () => {
  const location = useLocation();
  const [ratingData, setRatingData] = useState(null);
  const [answers, setAnswers] = useState(null);
  const [user, setUser] = useState({ fullName: 'Иван', age: 18 });

  useEffect(() => {
    const storedRating = localStorage.getItem('rating');
    const storedAnswers = localStorage.getItem('surveyAnswers');
    const storedUser = localStorage.getItem('user');

    if (storedRating) setRatingData(JSON.parse(storedRating));
    if (storedAnswers) setAnswers(JSON.parse(storedAnswers));
    if (storedUser) setUser(JSON.parse(storedUser));

    if (location.state) {
      if (location.state.rating) setRatingData(location.state.rating);
      if (location.state.answers) setAnswers(location.state.answers);
      if (location.state.user) setUser(location.state.user);
    }
  }, [location.state]);

  if (!ratingData || !answers) {
    return (
      <div style={{ maxWidth: '700px', margin: '2rem auto', padding: '0 1rem', textAlign: 'center' }}>
        <h2 style={{ color: '#07521f' }}>Профиль</h2>
        <p>Данные не найдены. Пройдите анкетирование.</p>
      </div>
    );
  }

  const { score, details } = ratingData;
  const recommendations = generateRecommendations(answers, details);

  const scorePercent = Math.max(0, Math.min(Number(score) || 0, 100));
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
              <h2>{firstName}, {answers.age || 18} лет</h2>
              <strong>{scorePercent}<span>/100</span></strong>
            </div>
          </section>

          <section className="profile-factors">
            <h2>Факторы оценки</h2>
            {Object.entries(details).map(([key, value]) => (
              <div className="profile-factor" key={key}><span>{key}</span><strong>{value}</strong></div>
            ))}
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
