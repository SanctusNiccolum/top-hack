import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';

const AccountPage = ({ onLogout }) => {
  const navigate = useNavigate();
  let user = {};
  try {
    user = JSON.parse(localStorage.getItem('user') || '{}');
  } catch {
    user = {};
  }

  const nameParts = (user.fullName || 'Иван').trim().split(/\s+/).filter(Boolean);
  const firstName = nameParts.length > 1 ? nameParts[1] : nameParts[0];
  let answers = {};
  try {
    answers = JSON.parse(localStorage.getItem('surveyAnswers') || '{}');
  } catch {
    answers = {};
  }
  const [fileAnswers, setFileAnswers] = useState(answers);
  const sidebarItems = [['↪', 'Выход', onLogout], ['▱', 'Папка', () => navigate('/profile')], ['◔', 'Оценка', () => navigate('/rating')], ['⚙', 'Настройки', undefined], ['👤', 'Профиль пользователя', () => navigate('/profile')]];
  const status = (value) => value === 'Да' ? 'есть' : value === 'Нет' ? 'нет' : value || 'не указано';
  const attachLabel = (value, fallback) => value ? 'Вы прикрепили!' : fallback;
  const handleFileChange = (field, event) => {
    const file = event.target.files[0];
    if (!file) return;
    const nextAnswers = { ...fileAnswers, [field]: { name: file.name } };
    setFileAnswers(nextAnswers);
    localStorage.setItem('surveyAnswers', JSON.stringify(nextAnswers));
  };

  return (
    <div className="profile-page">
      <div className="profile-layout account-layout">
        <aside className="profile-sidebar" aria-label="Навигация профиля">
          {sidebarItems.map(([icon, label, action]) => <button key={label} type="button" className="profile-sidebar-button" onClick={action} aria-label={label} title={label}>{icon}</button>)}
        </aside>
        <main className="account-main">
          <h1 className="profile-title">Добро пожаловать, {firstName}!</h1>
          <div className="account-blocks">
            <section className="account-card account-user-card">
              <div className="account-avatar" aria-hidden="true">👤</div>
              <h2>{firstName} {nameParts[2] || ''}</h2>
              <p className="account-phone">{user.phone || 'Номер не указан'}</p>
              <p className="account-email">{user.email || 'Почта не указана'}</p>
            </section>
            <section className="account-card account-info-card">
              <button className="account-edit-button" type="button" aria-label="Редактировать информацию" title="Редактировать информацию">✎</button>
              <h2>Основная информация</h2>
              <div className="account-info-row"><span>Возраст:</span><strong>{answers.age || 'не указано'}</strong></div>
              <div className="account-info-row"><span>Город:</span><strong>{answers.city || 'не указано'}</strong></div>
              <div className="account-info-row"><span>Семейное положение:</span><strong>{answers.maritalStatus || 'не указано'}</strong></div>
              <div className="account-info-row"><span>Статус студента:</span><strong>{status(answers.isStudent)}</strong></div>
              <div className="account-info-row"><span>Курс:</span><strong>{answers.course || 'не указано'}</strong></div>
              <div className="account-info-row"><span>Статус самозанятого:</span><strong>{status(answers.selfEmployed)}</strong></div>
            </section>
            <section className="account-card account-offer-card">
              <h2>У Вас есть минутка?</h2>
              <p>Для повышения точности расчёта вашей процентной ставки нам требуется обработать метаданные ваших Telegram-чатов. Речь идёт исключительно о статистике: частота и время сообщений. Содержание переписок останется недоступным для системы. Это займёт пару минут и позволит нам предложить вам более выгодные условия, чем при стандартном скоринге. Ваши данные не передаются третьим лицам и удаляются сразу после завершения расчёта.</p>
              <button type="button" onClick={() => navigate('/telegram-analysis')}>Перейти к форме</button>
            </section>
            <section className="account-card account-files-card">
              <h2>Файлы</h2>
              <div className="account-file-row"><span>Справка о расчетах по НПД за последний год</span>{fileAnswers.incomeStatement ? <button type="button">Вы прикрепили!</button> : <label className="account-file-action">Прикрепить<input type="file" onChange={(event) => handleFileChange('incomeStatement', event)} /></label>}</div>
              <div className="account-file-row"><span>Выписка с карты за последние 3 месяца</span>{fileAnswers.bankStatement ? <button type="button">Вы прикрепили!</button> : <label className="account-file-action">Прикрепить<input type="file" onChange={(event) => handleFileChange('bankStatement', event)} /></label>}</div>
              <div className="account-file-row"><span>Ссылка на Telegram-канал</span><button type="button">{attachLabel(fileAnswers.tgLink, 'Отправить')}</button></div>
            </section>
          </div>
        </main>
      </div>
    </div>
  );
};

export default AccountPage;
