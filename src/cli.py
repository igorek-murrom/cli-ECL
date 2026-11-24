"""Конвертер варианта 15 из стандартного ввода в TOML."""

import argparse
import sys

import tomli_w

from config_parser import ConfigError, parse_config


def to_toml(text):
    """Разобрать конфигурацию и вернуть её представление в TOML."""
    root = parse_config(text)
    document = root if isinstance(root, dict) else {"value": root}
    return tomli_w.dumps(document)


def main():
    """Прочитать stdin, записать TOML в stdout или сообщить об ошибке."""
    parser = argparse.ArgumentParser(
        prog="run.sh",
        description="Преобразует конфигурацию варианта 15 из stdin в TOML."
    )
    parser.parse_args()
    try:
        output = to_toml(sys.stdin.read())
    except ConfigError as error:
        print(error, file=sys.stderr)
        return 1
    sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
