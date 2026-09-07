import React, { useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import styled from 'styled-components';
import { login, register } from '../api';

const Overlay = styled.div`
  position: fixed;
  inset: 0;
  z-index: 1000;

  display: flex;
  align-items: center;
  justify-content: center;

  padding: 20px;

  background: rgba(0, 0, 0, 0.55);
`;

const Modal = styled.div`
  width: min(100%, 460px);
  max-height: calc(100vh - 40px);
  overflow-y: auto;

  padding: 34px 32px 28px;

  background: #c3eddf;
  border-radius: 20px;

  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);

  position: relative;
`;

const CloseButton = styled.button`
  position: absolute;
  top: 12px;
  right: 16px;

  border: 0;
  background: transparent;

  color: #07521f;
  font-size: 25px;
  font-weight: 800;

  cursor: pointer;
`;

const Title = styled.h2`
  margin: 0 0 22px;

  color: #07521f;
  text-align: center;

  font-size: 34px;
  line-height: 1;
`;

const Input = styled.input`
  width: 100%;
  height: 48px;

  margin-bottom: 11px;
  padding: 0 10px;

  border: 0;
  border-radius: 6px;

  background: white;
  color: #07521f;

  font-family: inherit;
  font-size: 14px;

  outline: none;

  &:focus {
    box-shadow: 0 0 0 3px rgba(0, 183, 143, 0.35);
  }
`;

const Consent = styled.label`
  display: flex;
  align-items: flex-start;
  gap: 7px;

  margin: 3px 0 14px;

  color: #42665a;
  font-size: 10px;
  line-height: 1.25;

  cursor: pointer;
`;

const SocialTitle = styled.p`
  margin: 0 0 9px;

  text-align: center;

  color: #07521f;
  font-size: 11px;
  font-weight: 800;
`;

const Socials = styled.div`
  display: flex;
  justify-content: center;
  gap: 10px;
  margin-bottom: 18px;
`;

const SocialButton = styled.button`
  width: 32px;
  height: 32px;

  border: 0;
  border-radius: 50%;

  background: #46d8ba;
  color: white;

  font-size: 17px;
  font-weight: 900;

  cursor: pointer;
`;

const RegisterButton = styled.button`
  display: block;

  width: min(100%, 260px);
  height: 44px;

  margin: 0 auto;

  border: 0;
  border-radius: 6px;

  background: #ff8a00;
  color: white;

  font-family: inherit;
  font-size: 14px;
  font-weight: 900;

  cursor: pointer;

  &:hover {
    filter: brightness(1.05);
  }
`;

export default function RegistrationModal({ isOpen, mode, onClose, onSuccess }) {
  const isLogin = mode === 'login';
  const [fullName, setFullName] = useState('');
  const [phone, setPhone] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [agree, setAgree] = useState(false);
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!isOpen) return;

    const handleEscape = (event) => {
      if (event.key === 'Escape') {
        onClose();
      }
    };

    document.addEventListener('keydown', handleEscape);

    return () => {
      document.removeEventListener('keydown', handleEscape);
    };
  }, [isOpen, onClose]);

  if (!isOpen) {
    return null;
  }

  const handleOverlayClick = (event) => {
    if (event.target === event.currentTarget) {
      onClose();
    }
  };

  const validate = () => {
    const nextErrors = {};

    // Логин на бэкенде идёт по НОМЕРУ ТЕЛЕФОНА (см. LoginRequest), поэтому
    // телефон обязателен в обоих режимах, а email — только при регистрации,
    // он хранится в профиле и в аутентификации не участвует.
    if (!phone.trim()) nextErrors.phone = 'Введите номер телефона';

    if (!password) nextErrors.password = 'Введите пароль';
    // 8 символов — требование бэкенда, с 6 он ответит ошибкой валидации.
    else if (password.length < 8) nextErrors.password = 'Пароль должен быть не менее 8 символов';

    if (!isLogin) {
      if (!fullName.trim()) nextErrors.fullName = 'Введите ваше имя';
      if (!email) nextErrors.email = 'Введите email';
      else if (!/\S+@\S+\.\S+/.test(email)) nextErrors.email = 'Некорректный email';
      if (password !== confirmPassword) nextErrors.confirmPassword = 'Пароли не совпадают';
      if (!agree) nextErrors.agree = 'Необходимо согласие на обработку данных';
    }
    return nextErrors;
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    const nextErrors = validate();
    if (Object.keys(nextErrors).length > 0) {
      setErrors(nextErrors);
      return;
    }

    setBusy(true);
    setErrors({});

    // Раньше вход сверялся с localStorage — то есть был бутафорским.
    // Теперь это реальные запросы; обе функции сами сохраняют токен.
    let data;
    try {
      data = isLogin
        ? await login(phone.trim(), password)
        : await register(phone.trim(), password);
    } catch (err) {
      // При регистрации на занятый номер пробуем войти тем же паролем —
      // иначе повторный клик по «Зарегистрироваться» уводит в тупик.
      if (!isLogin && err.status === 409) {
        try {
          data = await login(phone.trim(), password);
        } catch (loginErr) {
          setErrors({ form: loginErr.message });
          setBusy(false);
          return;
        }
      } else {
        setErrors({ form: err.message });
        setBusy(false);
        return;
      }
    }
    setBusy(false);

    onSuccess(
      { email: email.trim(), phone: phone.trim(), fullName: fullName.trim(), mode },
      { isEnded: data.is_ended }
    );
    onClose();
    setFullName('');
    setPhone('');
    setEmail('');
    setPassword('');
    setConfirmPassword('');
    setAgree(false);
    setErrors({});
  };

  return (
    <Overlay
      role="presentation"
      onMouseDown={handleOverlayClick}
    >
      <Modal
        role="dialog"
        aria-modal="true"
        aria-labelledby="auth-modal-title"
      >
        <CloseButton
          type="button"
          aria-label={`Закрыть окно ${isLogin ? 'входа' : 'регистрации'}`}
          onClick={onClose}
        >
          ×
        </CloseButton>

        <Title id="auth-modal-title">
          {isLogin ? 'Вход' : 'Регистрация'}
        </Title>

        <form onSubmit={handleSubmit}>
          {!isLogin && <>
            <Input type="text" value={fullName} onChange={(event) => setFullName(event.target.value)} placeholder="ФИО" aria-label="ФИО" />
            {errors.fullName && <p className="form-error">{errors.fullName}</p>}
          </>}
          <Input type="tel" value={phone} onChange={(event) => setPhone(event.target.value)} placeholder="Номер телефона" aria-label="Номер телефона" autoComplete="tel" />
          {errors.phone && <p className="form-error">{errors.phone}</p>}
          {!isLogin && <>
            <Input type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="Адрес электронной почты" aria-label="Адрес электронной почты" />
            {errors.email && <p className="form-error">{errors.email}</p>}
          </>}
          <Input type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder={isLogin ? 'Пароль' : 'Придумайте пароль'} aria-label="Пароль" />
          {errors.password && <p className="form-error">{errors.password}</p>}
          {!isLogin && <>
            <Input type="password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} placeholder="Подтвердите пароль" aria-label="Подтвердите пароль" />
            {errors.confirmPassword && <p className="form-error">{errors.confirmPassword}</p>}
            <Consent>
              <input type="checkbox" checked={agree} onChange={(event) => setAgree(event.target.checked)} />
              <span>Я согласен на обработку персональных данных и с условиями политики.</span>
            </Consent>
            {errors.agree && <p className="form-error">{errors.agree}</p>}
          </>}
          {errors.form && <p className="form-error">{errors.form}</p>}

          <SocialTitle>или войдите с помощью:</SocialTitle>

          <Socials>
          <SocialButton
            type="button"
            aria-label="Войти через Telegram"
          >
            ➤
          </SocialButton>

          <SocialButton
            type="button"
            aria-label="Войти через другой сервис"
          >
            @
          </SocialButton>
          </Socials>

          <RegisterButton type="submit" disabled={busy}>
            {busy ? 'Отправляем…' : (isLogin ? 'Войти' : 'Зарегистрироваться')}
          </RegisterButton>
        </form>
      </Modal>
    </Overlay>
  );
}

RegistrationModal.propTypes = {
  isOpen: PropTypes.bool.isRequired,
  mode: PropTypes.oneOf(['registration', 'login']),
  onClose: PropTypes.func.isRequired,
  onSuccess: PropTypes.func.isRequired,
};

RegistrationModal.defaultProps = {
  mode: 'registration',
};