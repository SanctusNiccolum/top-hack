import React, { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { createReport } from '../api';

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
  const [report, setReport] = useState(null);
  const [answers, setAnswers] = useState(null);
  const [user, setUser] = useState({ fullName: 'Иван', age: 18 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    setAnswers(location.state?.answers || readStored('surveyAnswers', null));
    setUser(location.state?.user || readStored('user', { fullName: 'Иван', age: 18 }));

    // Скор считает бэкенд и отдаёт разбивку по трём веткам. Раньше он
    // считался здесь же на клиенте по своей формуле — числа расходились
    // с серверными.
    // Сумма ежемесячных платежей — ключевой вход формулы (ПДН). Без неё
    // база всегда равна 100 и анкетная ветка вырождается.
    const stored = JSON.parse(localStorage.getItem('surveyAnswers') || '{}');
    const monthlyPayments = Number.parseInt(stored.monthlyPayments, 10) || 0;

    createReport({ monthlyPayments })
      .then(setReport)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [location.state]);

  if (loading) {
    return <div className="profile-page profile-empty"><h2>Оценка</h2><p>Считаем оценку…</p></div>;
  }

  if (error || !report) {
    return (
      <div className="profile-page profile-empty">
        <h2>Оценка</h2>
        <p>{error || 'Данные не найдены.'}</p>
        <button type="button" onClick={() => navigate('/survey')}>Пройти анкету</button>
      </div>
    );
  }

  const score = Math.max(0, Math.min(Number(report.score) || 0, 100));

  // NULL означает, что ветка ещё не считалась — показываем это честно,
  // а не как ноль баллов (в итог она и не входит).
  const branches = [
    ['Анкета', report.survey_score],
    ['Банковская выписка', report.statement_score],
    ['Telegram', report.telegram_score]
  ];
  // answers может не быть (зашли на /rating напрямую, без прохождения
  // анкеты в этой сессии браузера) — скор всё равно придёт с бэкенда,
  // поэтому страницу не роняем, а показываем её без блока факторов.
  const survey = answers || {};

  const nameParts = (user.fullName || 'Иван').trim().split(/\s+/).filter(Boolean);
  const firstName = nameParts.length > 1 ? nameParts[1] : nameParts[0];
  const age = Number.parseInt(survey.age, 10) || 18;
  const ageWord = age % 10 === 1 && age % 100 !== 11 ? 'год' : [2, 3, 4].includes(age % 10) && ![12, 13, 14].includes(age % 100) ? 'года' : 'лет';
  // Объяснение приходит с бэкенда (по банковской выписке — разбор по
  // коэффициентам). Раньше советы были захардкожены на клиенте.
  const recommendations = (report.comment_from_ai || '')
    .split('\n')
    .filter((line) => line.trim())
    .map((line) => ({ title: '', text: line }));
  const income = parseInt(survey.monthlyIncome, 10) || 0;
  const regularIncome = ['Каждую неделю', '1-2 раза в месяц'].includes(survey.incomeFrequency);
  const hasRiskOperations = survey.paymentMethod === 'Криптовалюта' || Boolean(survey.paymentOther);
  const factorItems = [
    ['Доля наличных', survey.paymentMethod === 'Наличные' ? 8 : 3, false],
    ['Долговая нагрузка', survey.creditHistory === 'Нет, никогда' ? 9 : 5, false],
    ['Регулярность дохода', regularIncome ? 8 : 3, false],
    ['Концентрация оборота', ['Банковская карта', 'QR-код/СБП'].includes(survey.paymentMethod) ? 8 : 4, false],
    ['Кредитная история и риск-операции', hasRiskOperations || (survey.creditHistory || '').includes('микрозайм') ? -4 : 7, hasRiskOperations || (survey.creditHistory || '').includes('микрозайм')],
    ['Норма сбережений', income > 60000 ? 9 : income > 0 ? 4 : 0, false],
    ['Разнообразие трат по категориям', Math.min((survey.subscriptions || []).length * 2, 8), false],
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
          <section className="profile-factors rating-branches">
            <h2>Из чего сложилась оценка</h2>
            {branches.map(([label, value]) => (
              <div className="rating-factor-slider" key={label}>
                <div className="rating-factor-header">
                  <span>{label}</span>
                  <strong className={value === null ? 'negative' : 'positive'}>
                    {value === null ? 'не заполнено' : `${Number(value).toFixed(1)}/100`}
                  </strong>
                </div>
                <div className="rating-factor-track">
                  <div
                    className="rating-factor-fill positive"
                    style={{ width: `${value === null ? 0 : Number(value)}%` }}
                  />
                </div>
              </div>
            ))}
          </section>
          {answers && <section className="profile-factors rating-factors">
            <h2>Факторы оценки</h2>
            <div className="rating-factor-columns"><div>{factorItems.slice(0, 4).map(renderFactor)}</div><div>{factorItems.slice(4).map(renderFactor)}</div></div>
          </section>}
        </main>
        {recommendations.length > 0 && <aside className="profile-recommendations rating-recommendations"><h2><span className="recommendation-star" aria-hidden="true" />Рекомендации от<br />ИИ-ассистента</h2>{recommendations.map((recommendation, index) => <article className={`profile-recommendation recommendation-tone-${index % 4}`} key={index}><h3>{recommendation.title}</h3><p>{recommendation.text}</p></article>)}</aside>}
      </div>
    </div>
  );
};

export default RatingPage;
