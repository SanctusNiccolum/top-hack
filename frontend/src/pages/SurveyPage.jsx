import React, { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { completeAccount, updateAccount } from '../api';
import { surveyToAccount } from '../utils/surveyToAccount';

const SurveyPage = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [currentStep, setCurrentStep] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState('');
  const [answers, setAnswers] = useState({
    age: '',
    city: '',
    maritalStatus: '',
    isStudent: '',
    subscriptions: [],
    course: '',
    selfEmployed: '',
    incomeSource: '',
    monthlyIncome: '',
    incomeFrequency: '',
    incomeStatement: null,
    creditHistory: '',
    monthlyPayments: '',
    paymentMethod: '',
    paymentOther: '',
    overdue: '',
    bankStatement: null,
    tgLink: '',
    agreeToTerms: false,
  });

  const totalSteps = 4;

  const handleInputChange = (field, value) => {
    setAnswers((prev) => ({ ...prev, [field]: value }));
  };

  const handleCheckboxChange = (field, value) => {
    setAnswers((prev) => {
      const current = prev[field] || [];
      const newArray = current.includes(value)
        ? current.filter((item) => item !== value)
        : [...current, value];
      return { ...prev, [field]: newArray };
    });
  };

  const handleFileUpload = (field, file) => {
    setAnswers((prev) => ({ ...prev, [field]: file }));
  };

  const goNext = async () => {
    if (currentStep < totalSteps - 1) {
      setCurrentStep((prev) => prev + 1);
      return;
    }

    const storedUser = JSON.parse(localStorage.getItem('user') || '{}');
    const user = { ...storedUser, ...(location.state?.user || {}) };

    // Отправляем анкету на бэкенд: скор считает он, а не клиент.
    // Ответы дублируем в localStorage — их читают экраны профиля для
    // отображения (сами по себе они на скор больше не влияют).
    setSubmitting(true);
    setSubmitError('');
    try {
      await updateAccount(surveyToAccount(answers, user));
      await completeAccount();
    } catch (err) {
      setSubmitError(err.message);
      setSubmitting(false);
      return;
    }
    setSubmitting(false);

    localStorage.setItem('user', JSON.stringify(user));
    localStorage.setItem('surveyAnswers', JSON.stringify(answers));
    navigate('/rating', { state: { user, answers } });
  };

  const goBack = () => {
    if (currentStep > 0) setCurrentStep((prev) => prev - 1);
  };

  const isStepValid = (step) => {
    const errors = [];
    switch (step) {
      case 0:
        if (!answers.age.trim()) errors.push('Возраст');
        if (!answers.city.trim()) errors.push('Город');
        if (!answers.maritalStatus) errors.push('Семейное положение');
        if (!answers.isStudent) errors.push('Статус студента');
        if (answers.isStudent.startsWith('Да') && !answers.course) errors.push('Курс');
        break;
      case 1:
        if (!answers.selfEmployed) errors.push('Самозанятость');
        if (!answers.monthlyIncome.trim()) errors.push('Среднемесячный доход');
        if (!answers.incomeFrequency) errors.push('Частота дохода');
        break;
      case 2:
        if (!answers.creditHistory) errors.push('Кредитная история');
        if (!answers.paymentMethod) errors.push('Способ оплаты');
        if (!answers.overdue) errors.push('Просрочки');
        if (!answers.monthlyPayments.trim()) errors.push('Ежемесячные платежи по кредитам');
        break;
      case 3:
        if (!answers.tgLink.trim()) errors.push('Ссылка на Telegram');
        if (!answers.agreeToTerms) errors.push('Согласие на обработку');
        break;
      default:
        return { valid: true, errors: [] };
    }
    return { valid: errors.length === 0, errors };
  };

  const progress = ((currentStep + 1) / totalSteps) * 100;

  const renderStep = () => {
    switch (currentStep) {
      case 0:
        return <Step1 answers={answers} onChange={handleInputChange} onCheckboxChange={handleCheckboxChange} />;
      case 1:
        return <Step2 answers={answers} onChange={handleInputChange} onFileUpload={handleFileUpload} />;
      case 2:
        return <Step3 answers={answers} onChange={handleInputChange} />;
      case 3:
        return <Step4 answers={answers} onChange={handleInputChange} onFileUpload={handleFileUpload} onCheckboxChange={handleCheckboxChange} />;
      default:
        return null;
    }
  };

  const { valid } = isStepValid(currentStep);

  return (
    <div className="survey-page">
      <div className="survey-card">
        <div className="survey-progress" aria-label={`Прогресс: шаг ${currentStep + 1} из ${totalSteps}`}>
          <div className="survey-progress-value" style={{ width: `${progress}%` }} />
        </div>
        <div className="survey-card-content">
            <div className="survey-questions">{renderStep()}</div>

          <div className="survey-navigation">
          <button className="survey-back" onClick={goBack} disabled={currentStep === 0} aria-label="Назад">
            ←
          </button>
          <button className="survey-next" onClick={goNext} disabled={!valid || submitting}>
            {submitting
              ? 'Сохраняем…'
              : currentStep === totalSteps - 1 ? 'Завершить' : 'Далее ->'}
          </button>
        </div>
        {submitError && (
          <p className="form-error" role="alert" style={{ marginTop: '0.8rem' }}>
            Не удалось сохранить анкету: {submitError}
          </p>
        )}
        </div>
      </div>
    </div>
  );
};

const SurveyStepOne = ({ answers, onChange, onCheckboxChange }) => (
  <div>
    <div style={{ marginBottom: '1.5rem' }}>
      <label style={{ fontWeight: 'bold', display: 'block', marginBottom: '0.3rem' }}>Сколько вам лет?</label>
      <input type="text" value={answers.age} onChange={(event) => onChange('age', event.target.value)} style={{ width: '100%', padding: '0.6rem', borderRadius: '8px', border: '1px solid #ced4da' }} />
    </div>
    <div style={{ marginBottom: '1.5rem' }}>
      <label style={{ fontWeight: 'bold', display: 'block', marginBottom: '0.5rem' }}>Укажите ваше семейное положение.</label>
      {['Замужем/Женат', 'В гражданском браке', 'Не замужем/не женат'].map((option) => <label key={option} style={{ display: 'flex', alignItems: 'center', gap: '0.8rem', marginBottom: '0.4rem' }}><input type="radio" name="survey-maritalStatus" checked={answers.maritalStatus === option} onChange={() => onChange('maritalStatus', option)} />{option}</label>)}
    </div>
    <div>
      <label style={{ fontWeight: 'bold', display: 'block', marginBottom: '0.5rem' }}>Есть ли у вас платные подписки? (необязательно)</label>
      {['Да, на развлечения', 'Да, на образование', 'Да, на софт и сервисы', 'Да, на фитнес и здоровье', 'Нет, ни на что не подписан(а)', 'Не знаю точно'].map((option) => <label key={option} style={{ display: 'flex', alignItems: 'center', gap: '0.8rem', marginBottom: '0.3rem' }}><input type="checkbox" checked={answers.subscriptions.includes(option)} onChange={() => onCheckboxChange('subscriptions', option)} />{option}</label>)}
    </div>
  </div>
);

const SurveyStepTwo = ({ answers, onChange }) => (
  <div>
    <div style={{ marginBottom: '1.5rem' }}><label style={{ fontWeight: 'bold', display: 'block', marginBottom: '0.3rem' }}>В каком городе вы проживаете?</label><input type="text" value={answers.city} onChange={(event) => onChange('city', event.target.value)} style={{ width: '100%', padding: '0.6rem', borderRadius: '8px', border: '1px solid #ced4da' }} /></div>
    <div style={{ marginBottom: '1.5rem' }}><label style={{ fontWeight: 'bold', display: 'block', marginBottom: '0.5rem' }}>Являетесь ли вы студентом?</label>{['Да, очная форма', 'Да, очно-заочная/заочная форма', 'Нет'].map((option) => <label key={option} style={{ display: 'flex', alignItems: 'center', gap: '0.8rem', marginBottom: '0.4rem' }}><input type="radio" name="survey-isStudent" checked={answers.isStudent === option} onChange={() => { onChange('isStudent', option); if (option === 'Нет') onChange('course', ''); }} />{option}</label>)}</div>
    {answers.isStudent.startsWith('Да') && <div><label style={{ fontWeight: 'bold', display: 'block', marginBottom: '0.5rem' }}>На каком вы курсе?</label>{['1 курс', '2 курс', '3 курс', '4 курс', '5 курс', 'Магистратура/аспирантура'].map((option) => <label key={option} style={{ display: 'flex', alignItems: 'center', gap: '0.8rem', marginBottom: '0.3rem' }}><input type="radio" name="survey-course" checked={answers.course === option} onChange={() => onChange('course', option)} />{option}</label>)}</div>}
  </div>
);

const SurveyStepFour = ({ answers, onChange, onFileUpload, onCheckboxChange }) => (
  <div>
    <Step3 answers={answers} onChange={onChange} />
    <Step4 answers={answers} onChange={onChange} onFileUpload={onFileUpload} onCheckboxChange={onCheckboxChange} />
  </div>
);

// ---------- Старые компоненты шагов, сохранённые для совместимости ----------
const Step1 = ({ answers, onChange, onCheckboxChange }) => {
  return (
    <div>
      <div style={{ marginBottom: '1.5rem' }}>
        <label style={{ fontWeight: 'bold', display: 'block', marginBottom: '0.3rem' }}>Сколько вам лет?</label>
        <input
          type="text"
          value={answers.age}
          onChange={(e) => onChange('age', e.target.value)}
          style={{ width: '100%', padding: '0.6rem', borderRadius: '8px', border: '1px solid #ced4da' }}
        />
      </div>

      <div style={{ marginBottom: '1.5rem' }}>
        <label style={{ fontWeight: 'bold', display: 'block', marginBottom: '0.3rem' }}>В каком городе вы проживаете?</label>
        <input
          type="text"
          value={answers.city}
          onChange={(e) => onChange('city', e.target.value)}
          style={{ width: '100%', padding: '0.6rem', borderRadius: '8px', border: '1px solid #ced4da' }}
        />
      </div>

      <div style={{ marginBottom: '1.5rem' }}>
        <label style={{ fontWeight: 'bold', display: 'block', marginBottom: '0.5rem' }}>Укажите ваше семейное положение.</label>
        {['Замужем/Женат', 'В гражданском браке', 'Не замужем/не женат'].map((opt) => (
          <label key={opt} style={{ display: 'flex', alignItems: 'center', gap: '0.8rem', marginBottom: '0.4rem' }}>
            <input
              type="radio"
              name="maritalStatus"
              value={opt}
              checked={answers.maritalStatus === opt}
              onChange={() => onChange('maritalStatus', opt)}
            />
            {opt}
          </label>
        ))}
      </div>

      <div style={{ marginBottom: '1.5rem' }}>
        <label style={{ fontWeight: 'bold', display: 'block', marginBottom: '0.5rem' }}>Являетесь ли вы студентом?</label>
        {['Да, очная форма', 'Да, очно-заочная/заочная форма', 'Нет'].map((opt) => (
          <label key={opt} style={{ display: 'flex', alignItems: 'center', gap: '0.8rem', marginBottom: '0.4rem' }}>
            <input
              type="radio"
              name="isStudent"
              value={opt}
              checked={answers.isStudent === opt}
              onChange={() => onChange('isStudent', opt)}
            />
            {opt}
          </label>
        ))}
      </div>

      <div style={{ marginBottom: '1.5rem' }}>
        <label style={{ fontWeight: 'bold', display: 'block', marginBottom: '0.5rem' }}>Есть ли у вас платные подписки на какие-либо сервисы? (можно выбрать несколько)</label>
        {[
          'Да, на развлечения (например, Кинопоиск, Яндекс музыка, PS Plus)',
          'Да, на образование (например, Skillbox, Hemotours, Duolingo)',
          'Да, на софт и сервисы (например, Figma, OpenCode)',
          'Да, на фитнес и здоровье (например, абонемент в спортзал)',
          'Нет, ни на что не подписан(а)',
          'Не знаю точно',
        ].map((opt) => (
          <label key={opt} style={{ display: 'flex', alignItems: 'center', gap: '0.8rem', marginBottom: '0.3rem' }}>
            <input
              type="checkbox"
              checked={answers.subscriptions.includes(opt)}
              onChange={() => onCheckboxChange('subscriptions', opt)}
            />
            {opt}
          </label>
        ))}
      </div>

      <div>
        <label style={{ fontWeight: 'bold', display: 'block', marginBottom: '0.5rem' }}>На каком вы курсе?</label>
        {['1 курс', '2 курс', '3 курс', '4 курс', '5 курс', 'Магистратура/аспирантура'].map((opt) => (
          <label key={opt} style={{ display: 'flex', alignItems: 'center', gap: '0.8rem', marginBottom: '0.3rem' }}>
            <input
              type="radio"
              name="course"
              value={opt}
              checked={answers.course === opt}
              onChange={() => onChange('course', opt)}
            />
            {opt}
          </label>
        ))}
      </div>
    </div>
  );
};

// ---------- Шаг 2 ----------
const Step2 = ({ answers, onChange, onFileUpload }) => {
  return (
    <div>
      <div style={{ marginBottom: '1.5rem' }}>
        <label style={{ fontWeight: 'bold', display: 'block', marginBottom: '0.5rem' }}>Есть ли у вас официальная самозанятость? (налоговый режим НПД)</label>
        {['Да', 'Нет'].map((opt) => (
          <label key={opt} style={{ display: 'flex', alignItems: 'center', gap: '0.8rem', marginBottom: '0.3rem' }}>
            <input
              type="radio"
              name="selfEmployed"
              value={opt}
              checked={answers.selfEmployed === opt}
              onChange={() => onChange('selfEmployed', opt)}
            />
            {opt}
          </label>
        ))}
      </div>

      <div style={{ marginBottom: '1.5rem' }}>
        <label style={{ fontWeight: 'bold', display: 'block', marginBottom: '0.5rem' }}>Есть ли у вас источник дохода?</label>
        {['Работа по найму (официально)', 'Самозанятость/фриланс', 'Стипендия', 'Пенсия', 'Нет', 'Другое: ______'].map((opt) => (
          <label key={opt} style={{ display: 'flex', alignItems: 'center', gap: '0.8rem', marginBottom: '0.3rem' }}>
            <input
              type="radio"
              name="incomeSource"
              value={opt}
              checked={answers.incomeSource === opt}
              onChange={() => onChange('incomeSource', opt)}
            />
            {opt}
          </label>
        ))}
      </div>

      <div style={{ marginBottom: '1.5rem' }}>
        <label style={{ fontWeight: 'bold', display: 'block', marginBottom: '0.3rem' }}>Какой у вас среднемесячный доход? (в рублях)</label>
        <input
          type="text"
          value={answers.monthlyIncome}
          onChange={(e) => onChange('monthlyIncome', e.target.value)}
          style={{ width: '100%', padding: '0.6rem', borderRadius: '8px', border: '1px solid #ced4da' }}
          placeholder="Например: 50000"
        />
      </div>

      <div style={{ marginBottom: '1.5rem' }}>
        <label style={{ fontWeight: 'bold', display: 'block', marginBottom: '0.5rem' }}>Как часто вы получаете доход?</label>
        {['Каждую неделю', '1-2 раза в месяц', 'Раз 2-3 месяца', 'Нерегулярно/по проектам', 'Постоянного дохода нет'].map((opt) => (
          <label key={opt} style={{ display: 'flex', alignItems: 'center', gap: '0.8rem', marginBottom: '0.3rem' }}>
            <input
              type="radio"
              name="incomeFrequency"
              value={opt}
              checked={answers.incomeFrequency === opt}
              onChange={() => onChange('incomeFrequency', opt)}
            />
            {opt}
          </label>
        ))}
      </div>

      <div>
        <label style={{ fontWeight: 'bold', display: 'block', marginBottom: '0.3rem' }}>Прикрепите справку о состоянии расчетов (доходов) по налогу на профессиональный доход за последний год (если есть самозанятость)</label>
        <input
          type="file"
          onChange={(e) => onFileUpload('incomeStatement', e.target.files[0])}
          style={{ marginTop: '0.3rem' }}
        />
        {answers.incomeStatement && (
          <p style={{ color: '#28a745', marginTop: '0.5rem' }}>Файл выбран: {answers.incomeStatement.name}</p>
        )}
      </div>
    </div>
  );
};

// ---------- Шаг 3 ----------
const Step3 = ({ answers, onChange }) => {
  return (
    <div>
      <div style={{ marginBottom: '1.5rem' }}>
        <label style={{ fontWeight: 'bold', display: 'block', marginBottom: '0.5rem' }}>Пользовались ли вы кредитами или займами раньше?</label>
        {['Да, брал(а) кредит в банке', 'Да, брал(а) студенческий кредит', 'Да, брал(а) микрозайм (МФО)', 'Да, пользовался рассрочкой', 'Нет, никогда'].map((opt) => (
          <label key={opt} style={{ display: 'flex', alignItems: 'center', gap: '0.8rem', marginBottom: '0.3rem' }}>
            <input
              type="radio"
              name="creditHistory"
              value={opt}
              checked={answers.creditHistory === opt}
              onChange={() => onChange('creditHistory', opt)}
            />
            {opt}
          </label>
        ))}
      </div>

      <div style={{ marginBottom: '1.5rem' }}>
        <label style={{ fontWeight: 'bold', display: 'block', marginBottom: '0.5rem' }}>Как вы обычно расплачиваетесь за покупки?</label>
        {['Наличные', 'Банковская карта', 'QR-код/СБП', 'Криптовалюта', 'Другое:'].map((opt) => (
          <label key={opt} style={{ display: 'flex', alignItems: 'center', gap: '0.8rem', marginBottom: '0.3rem' }}>
            <input
              type="radio"
              name="paymentMethod"
              value={opt}
              checked={answers.paymentMethod === opt}
              onChange={() => onChange('paymentMethod', opt)}
            />
            {opt}
          </label>
        ))}
        {answers.paymentMethod === 'Другое:' && (
          <input
            type="text"
            value={answers.paymentOther}
            onChange={(e) => onChange('paymentOther', e.target.value)}
            style={{ width: '100%', padding: '0.6rem', borderRadius: '8px', border: '1px solid #ced4da', marginTop: '0.5rem' }}
            placeholder="Укажите способ оплаты"
          />
        )}
      </div>

      <div style={{ marginBottom: '1.5rem' }}>
        <label style={{ fontWeight: 'bold', display: 'block', marginBottom: '0.3rem' }}>
          Сколько вы ежемесячно платите по кредитам, займам и рассрочкам? (в рублях, 0 — если ничего)
        </label>
        <input
          type="text"
          inputMode="numeric"
          value={answers.monthlyPayments}
          onChange={(e) => onChange('monthlyPayments', e.target.value)}
          placeholder="0"
          style={{ width: '100%', padding: '0.6rem', borderRadius: '8px', border: '1px solid #ced4da' }}
        />
      </div>

      <div>
        <label style={{ fontWeight: 'bold', display: 'block', marginBottom: '0.5rem' }}>Бывали ли у вас просрочки по платежам?</label>
        {['Да, были пару раз', 'Нет, никогда', 'Не знаю/не уверен(а)'].map((opt) => (
          <label key={opt} style={{ display: 'flex', alignItems: 'center', gap: '0.8rem', marginBottom: '0.3rem' }}>
            <input
              type="radio"
              name="overdue"
              value={opt}
              checked={answers.overdue === opt}
              onChange={() => onChange('overdue', opt)}
            />
            {opt}
          </label>
        ))}
      </div>
    </div>
  );
};

// ---------- Шаг 4 ----------
const Step4 = ({ answers, onChange, onFileUpload, onCheckboxChange }) => {
  return (
    <div>
      <div style={{ marginBottom: '1.5rem' }}>
        <label style={{ fontWeight: 'bold', display: 'block', marginBottom: '0.3rem' }}>Прикрепите выписку с карты за последние 3 месяца</label>
        <input
          type="file"
          onChange={(e) => onFileUpload('bankStatement', e.target.files[0])}
          style={{ marginTop: '0.3rem' }}
        />
        {answers.bankStatement && (
          <p style={{ color: '#28a745', marginTop: '0.5rem' }}>Файл выбран: {answers.bankStatement.name}</p>
        )}
      </div>

      <div style={{ marginBottom: '1.5rem' }}>
        <label style={{ fontWeight: 'bold', display: 'block', marginBottom: '0.3rem' }}>Прикрепите ссылку на ваш Telegram-канал</label>
        <input
          type="text"
          value={answers.tgLink}
          onChange={(e) => onChange('tgLink', e.target.value)}
          style={{ width: '100%', padding: '0.6rem', borderRadius: '8px', border: '1px solid #ced4da' }}
          placeholder="Например: https://t.me/mychannel"
        />
      </div>

      <div>
        <label style={{ display: 'flex', alignItems: 'flex-start', gap: '0.8rem', cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={Boolean(answers.agreeToTerms)}
            // onCheckboxChange здесь не подходит: он для ГРУПП чекбоксов и
            // хранит значение массивом, из-за чего булев флаг только
            // включался и никогда не снимался (массив оставался непустым).
            onChange={(event) => onChange('agreeToTerms', event.target.checked)}
            style={{ marginTop: '3px' }}
          />
          <span>
            Я согласен на обработку моих персональных данных и данных Telegram-канала. Я прочитал{' '}
            <a href="/privacy-policy" style={{ color: '#ff8a00' }}>политику в отношении обработки персональных данных</a> и согласен с её положением.
          </span>
        </label>
      </div>
    </div>
  );
};

export default SurveyPage;
