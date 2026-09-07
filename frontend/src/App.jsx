import React, { useEffect, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import { Navigate, Route, Routes, useNavigate } from 'react-router-dom';
import styled, { keyframes } from 'styled-components';
import { onCLS, onINP, onLCP } from 'web-vitals';
import { themeConfig } from './theme/config.js';
import RegistrationModal from './components/RegistrationModal';
import AccountPage from './pages/AccountPage';
import ProfilePage from './pages/ProfilePage';
import StatementUploadPage from './pages/StatementUploadPage';
import RatingPage from './pages/RatingPage';
import SurveyPage from './pages/SurveyPage';
import TelegramAnalysisPage from './pages/TelegramAnalysisPage';


const fadeUp = keyframes`
  from { opacity: 0; transform: translateY(24px); }
  to { opacity: 1; transform: translateY(0); }
`;

const Section = styled.section`
  width: min(var(--page-width), calc(100% - var(--page-side-padding) * 2));
  margin-inline: auto;
`;

function Brand({ size, gap }) {
  return (
    <a className="brand" href="#top" aria-label="Дикие ягодки — на главную" style={{ '--brand-size': `${size}px`, '--brand-gap': `${gap}px` }}>
      ♧ <span>Дикие ягодки</span>
    </a>
  );
}
Brand.propTypes = { size: PropTypes.number, gap: PropTypes.number };
Brand.defaultProps = { size: 14, gap: 7 };

function Header({ height, buttonSize, buttonRadius, buttonPaddingX, buttonPaddingY, onLogin }) {
  return (
    <header className="topbar" id="top" style={{ '--topbar-height': `${height}px` }}>
      <div className="topbar-inner">
        <Brand size={buttonSize} gap={7} />
        <button className="login-mini" type="button" onClick={onLogin} style={{ borderRadius: buttonRadius, padding: `${buttonPaddingY}px ${buttonPaddingX}px`, fontSize: `${buttonSize}px` }}>Вход</button>
      </div>
    </header>
  );
}
Header.propTypes = {
  height: PropTypes.number,
  buttonSize: PropTypes.number,
  buttonRadius: PropTypes.number,
  buttonPaddingX: PropTypes.number,
  buttonPaddingY: PropTypes.number,
  onLogin: PropTypes.func.isRequired
};
Header.defaultProps = { height: 56, buttonSize: 13, buttonRadius: 7, buttonPaddingX: 14, buttonPaddingY: 7 };

function Button({ children, variant = 'orange', fontSize, paddingX, paddingY, radius, minWidth, onClick }) {
  return (
    <button
      className={`btn btn-${variant}`}
      type="button"
      onClick={onClick}
      style={{ fontSize: `${fontSize}px`, padding: `${paddingY}px ${paddingX}px`, borderRadius: radius, minWidth: minWidth || undefined }}
    >
      {children}
    </button>
  );
}
Button.propTypes = {
  children: PropTypes.node.isRequired,
  variant: PropTypes.oneOf(['orange', 'yellow', 'mint']),
  fontSize: PropTypes.number,
  paddingX: PropTypes.number,
  paddingY: PropTypes.number,
  radius: PropTypes.number,
  minWidth: PropTypes.number,
  onClick: PropTypes.func
};
Button.defaultProps = { variant: 'orange', fontSize: 14, paddingX: 20, paddingY: 10, radius: 8, minWidth: 0 };

function Hero({ heroTitleSize, leadSize, topPadding, bottomPadding, artMinHeight, buttonFontSize, buttonPaddingX, buttonPaddingY, buttonRadius, buttonGap, onOpenRegistration, onOpenLogin }) {
  return (
    <section className="hero" style={{ '--hero-top': `${topPadding}px`, '--hero-bottom': `${bottomPadding}px`, '--hero-title-size': `${heroTitleSize}px`, '--hero-lead-size': `${leadSize}px`, '--hero-art-height': `${artMinHeight}px`, '--hero-button-gap': `${buttonGap}px` }}>
      <Section>
        <div className="hero-grid">
          <div className="hero-copy">
            <p className="eyebrow">Бесплатно · Конфиденциально</p>
            <h1>Платформа управления<br className="desktop" /> своим рейтингом<br className="desktop" /> платежеспособности</h1>
            <p className="hero-lead">Пройдите короткий опрос —<br className="desktop" /> и за 5 минут узнайте, по плечу ли Вам кредит.</p>
            <div className="hero-actions">
                  <Button onClick={onOpenRegistration} fontSize={16} paddingX={24} paddingY={13} radius={buttonRadius}>Пройти опрос</Button>
                  <Button onClick={onOpenLogin} variant="yellow" fontSize={16} paddingX={24} paddingY={13} radius={buttonRadius}>Вход</Button>
            </div>
            <p className="privacy">Бесплатно·Конфиденциально</p>
          </div>
          <div className="hero-art" aria-hidden="true">
            <div className="screen"><div className="screen-line wide" /><div className="screen-line" /><div className="screen-line short" /><div className="screen-chart"><i /><i /><i /><i /></div></div>
            <div className="person person-one"><span className="head" /><span className="body" /><span className="leg l" /><span className="leg r" /></div>
            <div className="person person-two"><span className="head" /><span className="body" /><span className="leg l" /><span className="leg r" /></div>
            <div className="lamp">⌁</div>
          </div>
        </div>
      </Section>
    </section>
  );
}
Hero.propTypes = {
  heroTitleSize: PropTypes.number, leadSize: PropTypes.number, topPadding: PropTypes.number, bottomPadding: PropTypes.number,
  artMinHeight: PropTypes.number, buttonFontSize: PropTypes.number, buttonPaddingX: PropTypes.number, buttonPaddingY: PropTypes.number,
  buttonRadius: PropTypes.number, buttonGap: PropTypes.number, onOpenRegistration: PropTypes.func.isRequired, onOpenLogin: PropTypes.func.isRequired
};
Hero.defaultProps = { heroTitleSize: 71, leadSize: 20, topPadding: 55, bottomPadding: 28, artMinHeight: 320, buttonFontSize: 14, buttonPaddingX: 20, buttonPaddingY: 10, buttonRadius: 8, buttonGap: 10 };

const scoreItems = [
  ['Долговая нагрузка', '+6 баллов'],
  ['Регулярность дохода', '+8 баллов'],
  ['Рейтинг Telegram', '+5 баллов']
];

function ScoreCard({ width, padding, radius, scoreSize, rowGap, pointsPaddingX, pointsPaddingY, recommendationSize, recommendationRadius }) {
  return (
    <div className="score-card" style={{ '--score-width': `${width}px`, '--score-padding': `${padding}px`, '--score-radius': `${radius}px`, '--score-size': `${scoreSize}px`, '--score-row-gap': `${rowGap}px`, '--points-x': `${pointsPaddingX}px`, '--points-y': `${pointsPaddingY}px`, '--recommendation-size': `${recommendationSize}px`, '--recommendation-radius': `${recommendationRadius}px` }}>
      <div className="score-label">Пример анализа</div>
      <div className="score-user">Иван, 18 лет</div>
      <div className="score-value">82<span>/100</span></div>
      <div className="score-caption">общая оценка платежеспособности</div>
      <div className="score-list">
        {scoreItems.map(([name, points]) => <div className="score-row" key={name}><strong>{name}</strong><span>{points}</span></div>)}
      </div>
      <Button variant="mint" fontSize={recommendationSize} paddingX={12} paddingY={10} radius={recommendationRadius}>⚙ Рекомендации от ИИ-ассистента</Button>
    </div>
  );
}
ScoreCard.propTypes = {
  width: PropTypes.number, padding: PropTypes.number, radius: PropTypes.number, scoreSize: PropTypes.number, rowGap: PropTypes.number,
  pointsPaddingX: PropTypes.number, pointsPaddingY: PropTypes.number, recommendationSize: PropTypes.number, recommendationRadius: PropTypes.number
};
ScoreCard.defaultProps = { width: 440, padding: 18, radius: 27, scoreSize: 56, rowGap: 11, pointsPaddingX: 10, pointsPaddingY: 6, recommendationSize: 12, recommendationRadius: 7 };

function Features({ sectionTitleSize, sectionPaddingTop, sectionPaddingBottom, columnsGap, noteWidth, notePadding, noteRadius, noteFontSize, noteTitleSize, centerWidth, centerScale, scoreCardWidth, scoreCardPadding, scoreCardRadius, scoreSize, scoreRowGap, pointsPaddingX, pointsPaddingY, recommendationSize, recommendationRadius }) {
  return (
    <section className="features-section" aria-labelledby="features-title" style={{ '--section-title-size': `${sectionTitleSize}px`, '--section-top': `${sectionPaddingTop}px`, '--section-bottom': `${sectionPaddingBottom}px`, '--columns-gap': `${columnsGap}px`, '--note-width': `${noteWidth}px`, '--note-padding': `${notePadding}px`, '--note-radius': `${noteRadius}px`, '--note-font': `${noteFontSize}px`, '--note-title': `${noteTitleSize}px`, '--center-width': `${centerWidth}px`, '--center-scale': centerScale }}>
      <Section>
        <h2 id="features-title">Возможности сервиса</h2>
        <div className="feature-layout">
          <div className="feature-column left">
            <article className="feature-note"><h3>Пункты оценки</h3><p>Эти пункты помогут Вам определить и выставить баллы по системе альтернативного скоринга.</p></article>
            <article className="feature-note"><h3>Рейтинг Telegram</h3><p>Мы изучаем Ваш Telegram канал, для пошагового детального анализа и составления более полного рейтинга.</p></article>
          </div>
          <div className="feature-center" style={{ maxWidth: `${centerWidth}px`, transform: `scale(${centerScale})` }}><ScoreCard width={scoreCardWidth} padding={scoreCardPadding} radius={scoreCardRadius} scoreSize={scoreSize} rowGap={scoreRowGap} pointsPaddingX={pointsPaddingX} pointsPaddingY={pointsPaddingY} recommendationSize={recommendationSize} recommendationRadius={recommendationRadius} /></div>
          <div className="feature-column right">
            <article className="feature-note"><h3>Рекомендации от ИИ-ассистента</h3><p>Ваш помощник в повышении своего балла. Он поможет определить причины проблемного пункта, в которых Вы не смогли набрать максимальный балл.</p><p>Его алгоритмы скажут Ваши грани и сделают вывод о том, как повысить баллы Вашей платежеспособности.</p></article>
          </div>
        </div>
        <p className="section-footnote">*Также присутствуют другие способы анализа Вашей анкеты</p>
      </Section>
    </section>
  );
}
Features.propTypes = {
  sectionTitleSize: PropTypes.number, sectionPaddingTop: PropTypes.number, sectionPaddingBottom: PropTypes.number, columnsGap: PropTypes.number,
  noteWidth: PropTypes.number, notePadding: PropTypes.number, noteRadius: PropTypes.number, noteFontSize: PropTypes.number, noteTitleSize: PropTypes.number,
  centerWidth: PropTypes.number, centerScale: PropTypes.number
};
Features.defaultProps = { sectionTitleSize: 52, sectionPaddingTop: 58, sectionPaddingBottom: 65, columnsGap: 34, noteWidth: 300, notePadding: 14, noteRadius: 11, noteFontSize: 12, noteTitleSize: 16, centerWidth: 440, centerScale: 1 };

const faqs = [
  ['Что такое альтернативный скоринг?', 'Это оценка платежеспособности по дополнительным признакам, которые помогают дополнить классические финансовые показатели.'],
  ['Зачем мне знать рейтинг платежеспособности?', 'Он показывает, насколько устойчиво Ваше финансовое положение и насколько комфортно Вам будет обслуживать кредит.'],
  ['Что будет анализироваться в Telegram?', 'Только те данные, которые пользователь разрешает использовать для выбранного сценария анализа.'],
  ['Плохой рейтинг, как улучшить?', 'Сначала разберите факторы с наибольшим влиянием: долговую нагрузку, стабильность дохода и другие доступные показатели.'],
  ['Через сколько появятся результаты оценки?', 'Основной результат можно показать сразу после завершения анкеты; дополнительные рекомендации появляются по мере обработки данных.']
];

function FAQ({ sectionTitleSize, sectionPaddingTop, sectionPaddingBottom, cardWidth, cardRadius, rowHeight, questionSize, answerSize, ctaWidth, ctaRadius, ctaPaddingX, ctaPaddingY, ctaTitleSize, ctaButtonSize, ctaButtonPaddingX, ctaButtonPaddingY, ctaButtonRadius, onOpenRegistration }) {
  return (
    <section className="faq-section" aria-labelledby="faq-title" style={{ '--section-title-size': `${sectionTitleSize}px`, '--faq-top': `${sectionPaddingTop}px`, '--faq-bottom': `${sectionPaddingBottom}px`, '--faq-width': `${cardWidth}px`, '--faq-radius': `${cardRadius}px`, '--faq-row': `${rowHeight}px`, '--question-size': `${questionSize}px`, '--answer-size': `${answerSize}px`, '--cta-width': `${ctaWidth}px`, '--cta-radius': `${ctaRadius}px`, '--cta-x': `${ctaPaddingX}px`, '--cta-y': `${ctaPaddingY}px`, '--cta-title': `${ctaTitleSize}px` }}>
      <Section>
        <h2 id="faq-title">Отвечаем на вопросы</h2>
        <div className="faq-card">
          {faqs.map(([question, answer]) => <details key={question}><summary>{question}<span aria-hidden="true">⌄</span></summary><p>{answer}</p></details>)}
        </div>
        <div className="cta-card">
          <h3>Управляйте своей оценкой благополучия<br className="desktop" /> через альтернативный скоринг</h3>
          <Button onClick={onOpenRegistration} fontSize={ctaButtonSize} paddingX={ctaButtonPaddingX} paddingY={ctaButtonPaddingY} radius={ctaButtonRadius}>Попробовать бесплатно</Button>
        </div>
      </Section>
    </section>
  );
}
FAQ.propTypes = {
  sectionTitleSize: PropTypes.number, sectionPaddingTop: PropTypes.number, sectionPaddingBottom: PropTypes.number, cardWidth: PropTypes.number, cardRadius: PropTypes.number,
  rowHeight: PropTypes.number, questionSize: PropTypes.number, answerSize: PropTypes.number, ctaWidth: PropTypes.number, ctaRadius: PropTypes.number,
  ctaPaddingX: PropTypes.number, ctaPaddingY: PropTypes.number, ctaTitleSize: PropTypes.number, ctaButtonSize: PropTypes.number,
  ctaButtonPaddingX: PropTypes.number, ctaButtonPaddingY: PropTypes.number, ctaButtonRadius: PropTypes.number,
  onOpenRegistration: PropTypes.func.isRequired
};
FAQ.defaultProps = { sectionTitleSize: 52, sectionPaddingTop: 58, sectionPaddingBottom: 65, cardWidth: 700, cardRadius: 17, rowHeight: 56, questionSize: 14, answerSize: 14, ctaWidth: 700, ctaRadius: 18, ctaPaddingX: 24, ctaPaddingY: 18, ctaTitleSize: 16, ctaButtonSize: 14, ctaButtonPaddingX: 20, ctaButtonPaddingY: 10, ctaButtonRadius: 8 };

function Footer({ height, paddingX, fontSize }) {
  return <footer style={{ '--footer-height': `${height}px`, '--footer-pad': `${paddingX}px`, '--footer-font': `${fontSize}px` }}><div className="footer-inner"><Brand size={fontSize} gap={7} /><small>Политика в отношении обработки персональных данных<br />Согласие на обработку персональных данных</small><a href="#top" className="to-top">Наверх ↑</a></div></footer>;
}
Footer.propTypes = { height: PropTypes.number, paddingX: PropTypes.number, fontSize: PropTypes.number };
Footer.defaultProps = { height: 76, paddingX: 16, fontSize: 11 };

export default function App(props) {
  const [isRegistrationOpen, setIsRegistrationOpen] = useState(false);
  const [modalMode, setModalMode] = useState('registration');
  const [isAuthenticated, setIsAuthenticated] = useState(() => (
    localStorage.getItem('isAuthenticated') === 'true' || Boolean(localStorage.getItem('user'))
  ));
  const navigate = useNavigate();
  const openRegistration = () => {
    setModalMode('registration');
    setIsRegistrationOpen(true);
  };
  const openLogin = () => {
    setModalMode('login');
    setIsRegistrationOpen(true);
  };
  const closeRegistration = () => setIsRegistrationOpen(false);
  const handleLogin = (userData) => {
    setIsAuthenticated(true);
    localStorage.setItem('isAuthenticated', 'true');
    setIsRegistrationOpen(false);
    const registeredUser = { ...userData, registeredAt: new Date().toLocaleDateString() };
    localStorage.setItem('user', JSON.stringify(registeredUser));
    navigate('/survey', { state: { user: registeredUser } });
  };
  // Куда вести после входа, решает бэкенд: он возвращает is_ended.
  // Без заполненной анкеты расчёт рейтинга ответит ошибкой.
  const handleSignedIn = (userData, { isEnded } = {}) => {
    setIsAuthenticated(true);
    localStorage.setItem('isAuthenticated', 'true');
    setIsRegistrationOpen(false);

    const storedUser = JSON.parse(localStorage.getItem('user') || '{}');
    const user = { ...storedUser, ...userData };
    localStorage.setItem('user', JSON.stringify(user));

    navigate(isEnded ? '/rating' : '/survey', { state: { user } });
  };

  const handleLogout = () => {
    setIsAuthenticated(false);
    localStorage.removeItem('isAuthenticated');
    localStorage.removeItem('user');
    localStorage.removeItem('rating');
    localStorage.removeItem('surveyAnswers');
    navigate('/');
  };

  const config = { ...themeConfig, ...props };

  // Извлекаем все значения из config для удобства
  const {
    pageWidth, pageSidePadding,
    primaryColor, mintColor, orangeColor, yellowColor, pinkColor, creamColor, blackColor,
    lightMintColor, scoreBgColor, pointsBgColor, recommendationBgColor, ctaEndColor,
    bodyFontSize, bodyLineHeight,
    ...sectionProps
  } = config;

  // Всё остальное оставляем как есть, но используем sectionProps для дочерних компонентов
  const homePage = (
    <div style={{
      '--page-width': `${pageWidth}px`,
      '--page-side-padding': `${pageSidePadding}px`,
      '--primary-color': primaryColor,
      '--mint-color': mintColor,
      '--orange-color': orangeColor,
      '--yellow-color': yellowColor,
      '--pink-color': pinkColor,
      '--cream-color': creamColor,
      '--black-color': blackColor,
      '--light-mint-color': lightMintColor,
      '--score-bg-color': scoreBgColor,
      '--points-bg-color': pointsBgColor,
      '--recommendation-bg-color': recommendationBgColor,
      '--cta-end-color': ctaEndColor,
      '--body-font-size': `${bodyFontSize}px`,
      '--body-line-height': bodyLineHeight,
    }}>
      <Header {...sectionProps} onLogin={openLogin} />
      <main>
        <Hero {...sectionProps} onOpenRegistration={openRegistration} onOpenLogin={openLogin} />
        <Features {...sectionProps} />
        <FAQ {...sectionProps} onOpenRegistration={openRegistration} />
      </main>
      <Footer {...sectionProps} />
      <RegistrationModal isOpen={isRegistrationOpen} mode={modalMode} onClose={closeRegistration} onSuccess={handleSignedIn} />
    </div>
  );

  return (
    <Routes>
      <Route path="/survey" element={isAuthenticated ? <SurveyPage /> : <Navigate to="/" replace />} />
      <Route path="/profile" element={isAuthenticated ? <AccountPage onLogout={handleLogout} /> : <Navigate to="/" replace />} />
      <Route path="/rating" element={isAuthenticated ? <RatingPage onLogout={handleLogout} /> : <Navigate to="/" replace />} />
      <Route path="/telegram-analysis" element={isAuthenticated ? <TelegramAnalysisPage /> : <Navigate to="/" replace />} />
      {/* Роут /telegram-chats ждёт TelegramChatsPage — фронтендер её ещё
          не прислал, без файла сборка падает. Вернуть вместе с ней. */}
      <Route path="/statement" element={isAuthenticated ? <StatementUploadPage /> : <Navigate to="/" replace />} />
      <Route path="*" element={homePage} />
    </Routes>
  );
}

App.propTypes = {
  pageWidth: PropTypes.number,
  pageSidePadding: PropTypes.number,
  primaryColor: PropTypes.string, mintColor: PropTypes.string, orangeColor: PropTypes.string, yellowColor: PropTypes.string,
  pinkColor: PropTypes.string, creamColor: PropTypes.string, blackColor: PropTypes.string, lightMintColor: PropTypes.string, scoreBgColor: PropTypes.string, pointsBgColor: PropTypes.string, recommendationBgColor: PropTypes.string, ctaEndColor: PropTypes.string,
  bodyFontSize: PropTypes.number, bodyLineHeight: PropTypes.number,
  height: PropTypes.number,
  buttonSize: PropTypes.number,
  buttonRadius: PropTypes.number,
  buttonPaddingX: PropTypes.number,
  buttonPaddingY: PropTypes.number,
  heroTitleSize: PropTypes.number,
  sectionTitleSize: PropTypes.number,
  leadSize: PropTypes.number,
  topPadding: PropTypes.number,
  bottomPadding: PropTypes.number,
  artMinHeight: PropTypes.number,
  buttonFontSize: PropTypes.number,
  buttonGap: PropTypes.number,
  sectionPaddingTop: PropTypes.number,
  sectionPaddingBottom: PropTypes.number,
  columnsGap: PropTypes.number,
  noteWidth: PropTypes.number,
  notePadding: PropTypes.number,
  noteRadius: PropTypes.number,
  noteFontSize: PropTypes.number,
  noteTitleSize: PropTypes.number,
  centerWidth: PropTypes.number,
  centerScale: PropTypes.number,
  cardWidth: PropTypes.number,
  cardRadius: PropTypes.number,
  rowHeight: PropTypes.number,
  questionSize: PropTypes.number,
  answerSize: PropTypes.number,
  ctaWidth: PropTypes.number,
  ctaRadius: PropTypes.number,
  ctaPaddingX: PropTypes.number,
  ctaPaddingY: PropTypes.number,
  ctaTitleSize: PropTypes.number,
  ctaButtonSize: PropTypes.number,
  ctaButtonPaddingX: PropTypes.number,
  ctaButtonPaddingY: PropTypes.number,
  ctaButtonRadius: PropTypes.number,
  scoreCardWidth: PropTypes.number,
  scoreCardPadding: PropTypes.number,
  scoreCardRadius: PropTypes.number,
  scoreSize: PropTypes.number,
  scoreRowGap: PropTypes.number,
  pointsPaddingX: PropTypes.number,
  pointsPaddingY: PropTypes.number,
  recommendationSize: PropTypes.number,
  recommendationRadius: PropTypes.number
};