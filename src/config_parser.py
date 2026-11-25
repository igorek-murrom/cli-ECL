"""Разбор учебного конфигурационного языка варианта 15."""

from decimal import Decimal, InvalidOperation

from lark import Lark, Transformer, v_args
from lark.exceptions import (
    UnexpectedCharacters,
    UnexpectedInput,
    VisitError,
)

_PARSER = Lark.open(
    "config.lark", rel_to=__file__, parser="lalr", maybe_placeholders=False
)


class ConfigError(ValueError):
    """Ошибка входной конфигурации с указанием позиции."""


def _error(line, column, message):
    """Сформировать сообщение с номером строки и столбца."""
    return ConfigError(f"Строка {line}, столбец {column}. {message}")


def _syntax_error(text, error):
    """Преобразовать ошибку Lark в сообщение о синтаксисе."""
    line, column = error.line, error.column
    if isinstance(error, UnexpectedCharacters):
        detail = f"Неожиданный символ {error.char!r}."
    elif error.token.type == "$END":
        line = text.count("\n") + 1
        column = len(text.rsplit("\n", 1)[-1]) + 1
        detail = "Неожиданный конец ввода."
    else:
        detail = f"Неожиданный фрагмент {str(error.token)!r}."
    return _error(line, column, f"Синтаксическая ошибка. {detail}")


@v_args(inline=True)
class ConfigEvaluator(Transformer):
    """Вычислить значения дерева и обработать объявления констант."""

    def __init__(self):
        """Создать таблицу констант для одного документа."""
        super().__init__()
        self.constants = {}

    def start(self, *items):
        """Вернуть корневое значение после обработки объявлений."""
        return items[-1]

    def definition(self, name, value):
        """Сохранить вычисленное значение новой константы."""
        if name in self.constants:
            raise _error(
                name.line, name.column, f"Константа «{name}» уже объявлена."
            )
        self.constants[name] = value

    def reference(self, token):
        """Подставить значение ранее объявленной константы."""
        name = token.removeprefix("#{").removesuffix("}")
        if name not in self.constants:
            raise _error(
                token.line, token.column, f"Неизвестная константа «{name}»."
            )
        return self.constants[name]

    def number(self, token):
        """Преобразовать целое или десятичное число."""
        try:
            if "." in token or "e" in token.lower():
                return Decimal(token)
            return int(token)
        except (ValueError, InvalidOperation) as error:
            raise _error(
                token.line, token.column, "Число вне поддерживаемого диапазона."
            ) from error

    def string(self, token):
        """Снять кавычки и префикс со строкового литерала."""
        return token.removeprefix('@"').removesuffix('"')

    def array(self, *values):
        """Собрать вычисленные элементы массива."""
        return list(values)

    def pair(self, name, value):
        """Сохранить имя поля вместе с позицией и значением."""
        return name, value

    def dictionary(self, *pairs):
        """Собрать словарь и проверить, что имена полей уникальны."""
        fields = {}
        for name, value in pairs:
            if name in fields:
                raise _error(
                    name.line, name.column, f"Повтор поля «{name}»."
                )
            fields[str(name)] = value
        return fields


def parse_config(text):
    """Разобрать текст и вычислить корневое значение конфигурации."""
    try:
        tree = _PARSER.parse(text)
        return ConfigEvaluator().transform(tree)
    except UnexpectedInput as error:
        raise _syntax_error(text, error) from None
    except VisitError as error:
        if isinstance(error.orig_exc, ConfigError):
            raise error.orig_exc from None
        raise
