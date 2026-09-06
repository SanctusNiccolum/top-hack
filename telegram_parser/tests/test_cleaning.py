"""Unit tests for telegram_parser.cleaning — pure functions, no fakes needed."""
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from telegram_parser.cleaning import clean_message_text, MIN_WORDS


class CleanMessageTextTests(unittest.TestCase):

    def test_keeps_ordinary_long_message(self):
        text = "Работаю над новым проектом для клиента, много задач"
        self.assertEqual(clean_message_text(text), text)

    def test_drops_short_message(self):
        self.assertIsNone(clean_message_text("ок"))
        self.assertIsNone(clean_message_text("да норм"))

    def test_drops_empty_or_none(self):
        self.assertIsNone(clean_message_text(None))
        self.assertIsNone(clean_message_text(""))

    def test_strips_mention(self):
        out = clean_message_text("Мой контакт @ivan_petrov1990 знает детали проекта")
        self.assertNotIn("@ivan_petrov1990", out)

    def test_strips_formatted_phone(self):
        out = clean_message_text("Позвони мне +7 999 123-45-67 после обеда пожалуйста")
        self.assertNotIn("999", out)
        self.assertNotIn("123-45-67", out)

    def test_strips_unformatted_ru_mobile(self):
        out = clean_message_text("Наберите 89991234567 срочно по рабочему вопросу")
        self.assertNotIn("89991234567", out)

    def test_strips_email_cleanly_no_mangled_remainder(self):
        # Regression test: the email must be fully removed, not partially
        # eaten by the mention regex (which used to leave "test.ru" behind).
        out = clean_message_text("Напишите мне на почту test@mail.ru по поводу проекта")
        self.assertNotIn("@", out)
        self.assertNotIn("test", out)
        self.assertNotIn(".ru", out)

    def test_does_not_strip_short_unformatted_digit_runs(self):
        # Regression test: dates / order numbers / short IDs without any
        # phone-like formatting must survive (previously false-positived
        # as "phone numbers" by the old regex).
        cases = [
            "Дата рождения 15111990 у моего клиента по документам",
            "13001500 — номер заказа, уточните пожалуйста статус доставки",
        ]
        for text in cases:
            out = clean_message_text(text)
            digits = "".join(c for c in text if c.isdigit())
            self.assertIn(digits, out or "", msg=f"digits stripped from: {text!r} -> {out!r}")

    def test_does_not_strip_short_numeric_ranges(self):
        out = clean_message_text("Было 5-6 встреч на прошлой неделе, все прошли нормально")
        self.assertIn("5-6", out)

    def test_word_count_boundary(self):
        exactly_min = " ".join(["слово"] * MIN_WORDS)
        below_min = " ".join(["слово"] * (MIN_WORDS - 1))
        self.assertIsNotNone(clean_message_text(exactly_min))
        self.assertIsNone(clean_message_text(below_min))


if __name__ == "__main__":
    unittest.main()
