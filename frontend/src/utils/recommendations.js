/**
 * Рекомендации «как поднять оценку».
 *
 * Строятся из того, что реально посчитал бэкенд, а не из захардкоженных
 * советов: негативные факторы Telegram-анализа (категория + вклад в
 * поправку) плюс разбор коэффициентов по банковской выписке.
 *
 * Тексты советов живут здесь, а не на бэкенде, потому что это часть
 * интерфейса: формулировки меняются вместе с UX, а не с моделью скоринга.
 */

// Категории приходят из tg-ai (см. tg_scoring/categories.py).
const ADVICE = {
  gambling: {
    title: 'Ставки и азартные игры',
    text: 'Это самый весомый негативный фактор в оценке. Банки трактуют регулярные ставки как риск потери дохода. Если упоминаний станет меньше, оценка вырастет заметнее всего.'
  },
  microloan_reliance: {
    title: 'Микрозаймы',
    text: 'Обращение к МФО читается как нехватка подушки безопасности. Закрытие текущих займов и отказ от новых — самый быстрый способ убрать этот фактор.'
  },
  debt_distress: {
    title: 'Сложности с платежами',
    text: 'Упоминания просрочек и нехватки денег к концу месяца снижают оценку. Помогает даже небольшой, но регулярный резерв на обязательные платежи.'
  },
  job_loss: {
    title: 'Потеря работы',
    text: 'Перерыв в занятости снижает оценку. Как только появятся упоминания стабильной работы, фактор перестанет действовать.'
  },
  income_instability: {
    title: 'Нестабильный доход',
    text: 'Нерегулярные поступления оцениваются хуже предсказуемых. Помогают постоянные клиенты или подработка с фиксированным графиком.'
  },
  impulsive_spending: {
    title: 'Импульсивные траты',
    text: 'Спонтанные покупки читаются как слабый контроль расходов. Планирование бюджета на месяц убирает этот сигнал.'
  },
  subscription_gambling: {
    title: 'Подписки на каналы ставок',
    text: 'Подписки на букмекеров и азартные каналы учитываются как фактор риска. Отписка от них поднимет оценку.'
  },
  subscription_microloan: {
    title: 'Подписки на каналы микрозаймов',
    text: 'Каналы МФО в подписках читаются как готовность занимать под высокий процент.'
  },
  subscription_crypto: {
    title: 'Криптоканалы в подписках',
    text: 'Интерес к криптовалютам оценивается как повышенный риск: доход из этого источника нестабилен.'
  },
  risky_investment: {
    title: 'Рискованные вложения',
    text: 'Упоминания торговли с плечом и обещаний быстрой прибыли повышают оценку риска.'
  }
};

const POSITIVE_HINT = {
  subscription_finance: 'подписки на финансовые каналы',
  subscription_education: 'подписки на образовательные каналы',
  subscription_job: 'подписки на каналы о работе',
  employment_stable: 'стабильная занятость',
  income_regular: 'регулярный доход',
  obligation_fulfilled: 'исполнение обязательств',
  financial_planning: 'финансовое планирование',
  education_active: 'обучение',
  business_activity: 'деловая активность',
  long_horizon_planning: 'планирование на длинном горизонте'
};

/**
 * @param {object} report ответ POST /report
 * @returns {{title: string, text: string}[]}
 */
export function buildRecommendations(report = {}) {
  const items = [];
  const factors = Array.isArray(report.telegram_factors) ? report.telegram_factors : [];

  // Сначала то, что тянет оценку вниз — по убыванию вклада: человеку
  // полезнее знать, с чего начать, а не полный перечень.
  const negative = factors
    .filter((factor) => Number(factor.contribution) < 0)
    .sort((a, b) => Number(a.contribution) - Number(b.contribution));

  for (const factor of negative) {
    const advice = ADVICE[factor.category];
    if (!advice) continue;
    items.push({
      title: advice.title,
      text: `${advice.text} Сейчас этот фактор снижает оценку на ${Math.abs(Number(factor.contribution)).toFixed(1)} балла (упоминаний: ${factor.evidence_count}).`
    });
  }

  // Затем — что уже работает в плюс, чтобы человек это не потерял.
  const positive = factors
    .filter((factor) => Number(factor.contribution) > 0)
    .sort((a, b) => Number(b.contribution) - Number(a.contribution))
    .map((factor) => POSITIVE_HINT[factor.category])
    .filter(Boolean);

  if (positive.length > 0) {
    items.push({
      title: 'Что уже работает в плюс',
      text: `В вашу пользу говорят: ${positive.join(', ')}. Эти сигналы стоит сохранить — именно они удерживают оценку.`
    });
  }

  // Разбор по банковской выписке приходит готовым текстом с бэкенда.
  const statementLines = (report.comment_from_ai || '')
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean);

  if (statementLines.length > 1) {
    items.push({
      title: 'По банковской выписке',
      text: statementLines.slice(1).join(' ')
    });
  }

  if (items.length === 0) {
    items.push({
      title: 'Данных пока мало',
      text: 'Загрузите выписку и подключите Telegram — тогда мы сможем объяснить оценку и подсказать, что именно её повышает.'
    });
  }

  return items;
}

export default buildRecommendations;
