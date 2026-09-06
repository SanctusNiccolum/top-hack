/**
 * Перевод ответов анкеты в поля бэкенда.
 *
 * Анкета хранит ответы человеческими строками («Замужем/Женат»), а
 * бэкенд принимает enum-коды (`MARRIED`). Держим сопоставление одним
 * файлом: если в анкете поменяется формулировка, чинить нужно будет
 * только здесь, а не искать по компонентам.
 *
 * Неизвестное значение превращается в undefined и просто не уходит на
 * бэкенд — там все поля анкеты необязательные, поэтому частично
 * заполненная анкета сохранится, а не свалится с ошибкой валидации.
 */

const FAMILY_STATUS = {
  'Замужем/Женат': 'MARRIED',
  'В гражданском браке': 'CIVIL_MARRIAGE',
  'Не замужем/не женат': 'SINGLE'
};

const STUDENT_STATUS = {
  'Да, очная форма': 'FULL_TIME',
  'Да, очно-заочная/заочная форма': 'PART_TIME',
  Нет: 'NOT_STUDENT'
};

const STUDENT_COURSE = {
  '1 курс': 'FIRST',
  '2 курс': 'SECOND',
  '3 курс': 'THIRD',
  '4 курс': 'FOURTH',
  '5 курс': 'FIFTH',
  'Магистратура/аспирантура': 'MASTER_OR_POSTGRADUATE'
};

const INCOME_SOURCE = {
  'Работа по найму (официально)': 'EMPLOYMENT',
  'Самозанятость/фриланс': 'SELF_EMPLOYED',
  Стипендия: 'SCHOLARSHIP',
  Пенсия: 'PENSION',
  Нет: 'NONE',
  'Другое: ______': 'OTHER'
};

const INCOME_FREQUENCY = {
  'Каждую неделю': 'WEEKLY',
  '1-2 раза в месяц': 'ONE_TWO_TIMES_MONTH',
  'Раз 2-3 месяца': 'EVERY_TWO_THREE_MONTHS',
  'Нерегулярно/по проектам': 'IRREGULAR',
  'Постоянного дохода нет': 'NONE'
};

const CREDIT_HISTORY = {
  'Да, брал(а) кредит в банке': 'BANK_CREDIT',
  'Да, брал(а) студенческий кредит': 'STUDENT_CREDIT',
  'Да, брал(а) микрозайм (МФО)': 'MICROLOAN',
  'Да, пользовался рассрочкой': 'INSTALLMENT'
};

const PAYMENT_METHOD = {
  Наличные: 'CASH',
  'Банковская карта': 'BANK_CARD',
  'QR-код/СБП': 'SBP',
  Криптовалюта: 'CRYPTO',
  'Другое:': 'OTHER'
};

const PAYMENT_OVERDUE = {
  'Да, были пару раз': 'YES',
  'Нет, никогда': 'NO',
  'Не знаю/не уверен(а)': 'UNKNOWN'
};

const SUBSCRIPTIONS = {
  'Да, на развлечения': 'ENTERTAINMENT',
  'Да, на образование': 'EDUCATION',
  'Да, на софт и сервисы': 'SOFTWARE',
  'Да, на фитнес и здоровье': 'FITNESS',
  'Нет, ни на что не подписан(а)': 'NONE',
  'Не знаю точно': 'UNKNOWN'
};

/** Убирает ключи со значением undefined — их не нужно слать на бэкенд. */
function compact(object) {
  return Object.fromEntries(
    Object.entries(object).filter(([, value]) => value !== undefined && value !== '')
  );
}

export function surveyToAccount(answers = {}, user = {}) {
  const age = Number.parseInt(answers.age, 10);
  const income = Number.parseInt(answers.monthlyIncome, 10);

  // ФИО с формы регистрации приходит одной строкой «Фамилия Имя Отчество».
  const nameParts = (user.fullName || '').trim().split(/\s+/).filter(Boolean);

  return compact({
    last_name: nameParts[0],
    first_name: nameParts[1],
    patronymic: nameParts[2],
    email: user.email,

    age: Number.isFinite(age) ? age : undefined,
    city: answers.city || undefined,

    family_status: FAMILY_STATUS[answers.maritalStatus],
    student_status: STUDENT_STATUS[answers.isStudent],
    student_course: STUDENT_COURSE[answers.course],

    monthly_income: Number.isFinite(income) ? income : undefined,
    self_employed: answers.selfEmployed === 'Да' ? true
      : answers.selfEmployed === 'Нет' ? false : undefined,

    income_source: INCOME_SOURCE[answers.incomeSource],
    income_frequency: INCOME_FREQUENCY[answers.incomeFrequency],

    credit_history: CREDIT_HISTORY[answers.creditHistory],
    payment_overdue: PAYMENT_OVERDUE[answers.overdue],

    payment_method: PAYMENT_METHOD[answers.paymentMethod],
    payment_method_other: answers.paymentOther || undefined,

    subscriptions: Array.isArray(answers.subscriptions)
      ? answers.subscriptions.map((item) => SUBSCRIPTIONS[item]).filter(Boolean)
      : undefined
  });
}

export default surveyToAccount;
