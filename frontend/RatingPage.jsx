import React, { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { generateRecommendations } from '../utils/generateRecommendations';
import { calculateRating } from '../utils/calculateRating';

const readStored = (key, fallback) => {
  try {
    return JSON.parse(localStorage.getItem(key) || JSON.stringify(fallback));
  } catch {
    return fallback;
  }
};

const RatingPage = ({ onLogout }) => {
  const location = useLocation();
  const navigate = useNavigate();
  const [ratingData, setRatingData] = useState(null);
  const [answers, setAnswers] = useState(null);
  const [user, setUser] = useState({ fullName: 'Иван', age: 18 });

  useEffect(() => {
    const storedAnswers = location.state?.answers || readStored('surveyAnswers', null);
    setAnswers(storedAnswers);
    setRatingData(storedAnswers ? calculateRating(storedAnswers) : location.state?.rating || readStored('rating', null));
    setUser(location.state?.user || readStored('user', { fullName: 'Иван', age: 18 }));
  }, [location.state]);

  if (!ratingData || !answers) {
    return <div className="profile-page profile-empty"><h2>Оценка</h2><p>Данные не найдены. Пройдите анкетирование.</p></div>;
  }

  const score = Math.max(0, Math.min(Number(ratingData.score) || 0, 100));
  const nameParts = (user.fullName || 'Иван').trim().split(/\s+/).filter(Boolean);
  const firstName = nameParts.length > 1 ? nameParts[1] : nameParts[0];
  const age = Number.parseInt(answers.age, 10) || 18;
  const ageWord = age % 10 === 1 && age % 100 !== 11 ? 'год' : [2, 3, 4].includes(age % 10) && ![12, 13, 14].includes(age % 100) ? 'года' : 'лет';
  const recommendations = generateRecommendations(answers, ratingData.details || {});
  const income = parseInt(answers.monthlyIncome, 10) || 0;
  const regularIncome = ['Каждую неделю', '1-2 раза в месяц'].includes(answers.incomeFrequency);
  const hasRiskOperations = answers.paymentMethod === 'Криптовалюта' || Boolean(answers.paymentOther);
  const factorItems = [
    ['Доля наличных', answers.paymentMethod === 'Наличные' ? 8 : 3, false],
    ['Долговая нагрузка', answers.creditHistory === 'Нет, никогда' ? 9 : 5, false],
    ['Регулярность дохода', regularIncome ? 8 : 3, false],
    ['Концентрация оборота', ['Банковская карта', 'QR-код/СБП'].includes(answers.paymentMethod) ? 8 : 4, false],
    ['Кредитная история и риск-операции', hasRiskOperations || answers.creditHistory.includes('микрозайм') ? -4 : 7, hasRiskOperations || answers.creditHistory.includes('микрозайм')],
    ['Норма сбережений', income > 60000 ? 9 : income > 0 ? 4 : 0, false],
    ['Разнообразие трат по категориям', Math.min((answers.subscriptions || []).length * 2, 8), false],
  ];
  const formatPoints = (points) => `${points > 0 ? '+' : ''}${points} ${Math.abs(points) === 1 ? 'балл' : Math.abs(points) >= 2 && Math.abs(points) <= 4 ? 'балла' : 'баллов'}`;
  const renderFactor = ([label, points, isNegative]) => {
    const percentage = Math.min(Math.abs(points) / 10 * 66.6667, 66.6667);
    const isPositive = !isNegative && points >= 0;
    return (
      <div className="rating-factor-slider" key={label}>
        <div className="rating-factor-header"><span>{label}</span><strong className={isPositive ? 'positive' : 'negative'}>{formatPoints(points)}</strong></div>
        <div className="rating-factor-track"><div className={`rating-factor-fill ${isPositive ? 'positive' : 'negative'}`} style={{ width: `${percentage}%` }} /></div>
      </div>
    );
  };
  const sidebarItems = [['↪', 'Выход', onLogout], ['▱', 'Папка', () => navigate('/profile')], ['◔', 'Оценка', () => navigate('/rating')], ['⚙', 'Настройки', undefined], ['👤', 'Профиль пользователя', () => navigate('/profile')]];

  return (
    <div className="profile-page rating-page">
      <div className="profile-layout rating-layout">
        <aside className="profile-sidebar" aria-label="Навигация профиля">
          {sidebarItems.map(([icon, label, action]) => <button key={label} type="button" className="profile-sidebar-button" onClick={action} aria-label={label} title={label}>{icon}</button>)}
        </aside>
        <main className="profile-main rating-main">
          <h1 className="profile-title">Оценка благонадежности</h1>
          <section className="profile-score-panel">
            <div className="profile-chart-wrap"><div className="profile-chart" style={{ '--score-percent': `${score * 3.6}deg` }} /></div>
            <div className="profile-user-summary"><h2>{firstName}, {age} {ageWord}</h2><strong>{score}<span>/100</span></strong></div>
          </section>
          <section className="profile-factors rating-factors">
            <h2>Факторы оценки</h2>
            <div className="rating-factor-columns"><div>{factorItems.slice(0, 4).map(renderFactor)}</div><div>{factorItems.slice(4).map(renderFactor)}</div></div>
          </section>
        </main>
        {recommendations.length > 0 && <aside className="profile-recommendations rating-recommendations"><h2><span className="recommendation-star" aria-hidden="true" />Рекомендации от<br />ИИ-ассистента</h2>{recommendations.map((recommendation, index) => <article className={`profile-recommendation recommendation-tone-${index % 4}`} key={index}><h3>{recommendation.title}</h3><p>{recommendation.text}</p></article>)}</aside>}
      </div>
    </div>
  );
};

export default RatingPage;
