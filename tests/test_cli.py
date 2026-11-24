"""Проверки CLI и перевода конструкций варианта 15 в TOML."""

from decimal import Decimal
import os
from pathlib import Path
import subprocess
import sys
import tomllib
import unittest

_PROJECT = Path(__file__).resolve().parents[1]
_ERROR_EXIT = 1


class CliTests(unittest.TestCase):
    """Проверки программы через штатный сценарий запуска."""

    def run_cli(self, text, *arguments):
        """Запустить конвертер с указанным входным текстом."""
        return subprocess.run(
            [_PROJECT / "run.sh", *arguments],
            input=text,
            encoding="utf-8",
            capture_output=True,
            check=False,
            env={**os.environ, "PYTHON": sys.executable},
        )

    def assert_toml(self, text, expected):
        """Проверить успешный выход и содержимое результата TOML."""
        result = self.run_cli(text)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        parsed = tomllib.loads(result.stdout, parse_float=Decimal)
        self.assertEqual(parsed, expected)
        return parsed

    def assert_error(self, text, message, location=None):
        """Проверить диагностику и отсутствие результата при ошибке."""
        result = self.run_cli(text)
        self.assertEqual(result.returncode, _ERROR_EXIT)
        self.assertEqual(result.stdout, "")
        self.assertIn(message, result.stderr)
        if location:
            self.assertIn(location, result.stderr)

    def test_number_formats(self):
        """Проверить знаки, дроби, порядок и сохранение точности."""
        parsed = self.assert_toml(
            "[00042; -004; 1.; .5; -.25; 3e+2; 1E0; -.4E-2; "
            "1.2345678901234567890123456789; -0.0]",
            {
                "value": [
                    42, -4, Decimal("1.0"), Decimal("0.5"),
                    Decimal("-0.25"), Decimal("3e+2"), Decimal("1.0"),
                    Decimal("-0.004"),
                    Decimal("1.2345678901234567890123456789"),
                    Decimal("-0.0"),
                ],
            },
        )
        self.assertIs(type(parsed["value"][0]), int)
        self.assertIsInstance(parsed["value"][2], Decimal)
        self.assertIsInstance(parsed["value"][6], Decimal)
        self.assertTrue(parsed["value"][-1].is_signed())

    def test_strings(self):
        """Проверить пустую строку, кириллицу и буквальную обратную косую."""
        self.assert_toml(
            r'[@"Это строка"; @""; @"C:\data\new; #{ignored}"]',
            {"value": ["Это строка", "", r"C:\data\new; #{ignored}"]},
        )

    def test_empty_collections(self):
        """Проверить пустые массивы и словари на обоих уровнях."""
        self.assert_toml("dict()", {})
        self.assert_toml("[]", {"value": []})
        self.assert_toml(
            "dict(empty_array = [], empty_dict = dict())",
            {"empty_array": [], "empty_dict": {}},
        )

    def test_nested_collections(self):
        """Проверить смешанные массивы и многоуровневые словари."""
        self.assert_toml(
            'dict(route_2 = [1; [2; @"остановка"]; '
            'dict(points = [3; 4], next = dict(id = 5))])',
            {"route_2": [1, [2, "остановка"], {
                "points": [3, 4], "next": {"id": 5},
            }]},
        )

    def test_constant_values(self):
        """Проверить объявления и подстановку всех типов значений."""
        self.assert_toml(
            '(define count 3)\n(define title @"тест")\n'
            '(define items [#{count}; #{title}])\n'
            '(define table dict(list = #{items}))\n'
            '(define alias #{table})\n'
            'dict(count = #{count}, snapshots = [#{table}; #{alias}])',
            {"count": 3, "snapshots": [
                {"list": [3, "тест"]}, {"list": [3, "тест"]},
            ]},
        )

    def test_root_values(self):
        """Проверить вывод корневого словаря, числа и строки."""
        self.assert_toml("(define d dict(a = 1))\n#{d}", {"a": 1})
        self.assert_toml("(define n 7)\n#{n}", {"value": 7})
        self.assert_toml('@"корень"', {"value": "корень"})

    def test_syntax_errors(self):
        """Проверить ошибки в литералах, разделителях и объявлениях."""
        cases = (
            "dict(Upper = 1)", "dict(_key = 1)", "dict(2key = 1)",
            "dict(a: 1)", "dict(a = 1 b = 2)", "dict(a = 1,)",
            "[1, 2]", "[1;]", "[1 2]", "[1;;2]",
            "+2", "1e+", "2.3.4", "1_000",
            '"plain"', '@"unfinished', '@"two\nlines"',
            "(define x) dict()", "(definex 1) dict()", "#{x y}",
            "[(define x 1)]", "1 2", "", "(define a 1)",
        )
        for text in cases:
            with self.subTest(text=text):
                self.assert_error(text, "Синтаксическая ошибка")

    def test_error_locations(self):
        """Проверить позицию ошибки в токене и в конце документа."""
        self.assert_error(
            "dict(\n  key: 1\n)", "Синтаксическая ошибка",
            "Строка 2, столбец 6",
        )
        self.assert_error(
            "[1;\n", "Неожиданный конец ввода", "Строка 2, столбец 1"
        )

    def test_bad_declarations_and_references(self):
        """Проверить неизвестные константы и повторные объявления."""
        self.assert_error(
            "dict(a = #{missing})", "Неизвестная константа «missing»",
            "Строка 1, столбец 10",
        )
        self.assert_error(
            "(define a #{b})\n(define b 1)\n#{a}",
            "Неизвестная константа «b»",
        )
        self.assert_error(
            "(define a 1)\n(define a 2)\n#{a}", "уже объявлена",
            "Строка 2, столбец 9",
        )

    def test_duplicate_dictionary_key(self):
        """Проверить повторы в словаре и независимость разных словарей."""
        self.assert_error("[dict(a = 1, a = 2)]", "Повтор поля «a».")
        self.assert_toml(
            "[dict(a = 1); dict(a = 2)]", {"value": [{"a": 1}, {"a": 2}]}
        )

    def test_weather_example(self):
        """Проверить пример конфигурации метеостанции."""
        text = (_PROJECT / "examples/weather.cfg").read_text("utf-8")
        self.assert_toml(
            text,
            {
                "station": "Метеостанция Север",
                "interval_seconds": 30,
                "sensors": [
                    {
                        "name": "Температура", "unit": "°C",
                        "limits": {"minimum": -25, "maximum": 45},
                    },
                    {
                        "name": "Влажность", "unit": "%",
                        "limits": {"minimum": 0, "maximum": 100},
                    },
                ],
            },
        )

    def test_library_example(self):
        """Проверить пример конфигурации библиотеки."""
        text = (_PROJECT / "examples/library.cfg").read_text("utf-8")
        self.assert_toml(
            text,
            {
                "branch": "Городская библиотека",
                "catalogs": [
                    {"name": "Основной фонд", "loan_days": 21},
                    {"name": "Редкий фонд", "loan_days": 3},
                ],
                "circulation": {
                    "max_items": 5, "renewal_days": [7, 14],
                    "pickup_points": ["Стойка 1", "Стойка 2"],
                },
            },
        )

    def test_help(self):
        """Проверить доступность справки из командной строки."""
        result = self.run_cli("", "--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("TOML", result.stdout)
        self.assertEqual(result.stderr, "")
