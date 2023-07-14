#!/usr/bin/env python
# -*- coding: utf-8 -*-

import configparser
import datetime
import gzip
import os
import re
from statistics import mean, median
import string
import sys
import logging

# Default config
config = {
    "CONFIG_PATH": "config.ini",
    "REPORT_SIZE": 1000,
    "REPORT_DIR": "./reports",
    "LOG_DIR": "./log",
    "LOG_FILE": None,
    "LOGGING_LEVEL": "INFO",
    "ALLOW_ERROR_RATE": 0.1,
}


class LogAnalyzer:
    """Класс анализатора логов nginx"""

    def __init__(self, default_config, config_path) -> None:
        """Инициализация.

        Args:
            default_config (dict): Конфигурация по умолчанию.
            config_path (str): Путь к конфигурационному файлу.
        """
        self.config_path = config_path
        self.config = default_config
        self.config_update()
        self.logger = None
        self.init_logging()
        self.log_file_name_pattern = re.compile(
            "^(?P<file_name>nginx-access-ui\.log-(?P<file_date>\d{8}))(?P<file_ext>\.gz)?$"
        )
        self.log_line_pattern = re.compile(
            r"(\S+) (\S+)  (\S+) \[(.+)\] \"(.+)\" (\S+) (\S+) \"(\S+)\" \"(.+)\" \"(\S+)\" \"(\S+)\" \"(\S+)\" (\S+)"
        )
        self.log_strings_count = 0
        self.log_strings_parsed = 0
        self.log_strings_error = 0
        self.log_sum_time = 0
        self.report_data = {}
        self.file_date = None

    def config_update(self):
        """Обновить конфигурацию"""
        if self.config_path is None:
            pass
        elif os.path.exists(self.config_path):
            read_config = self.get_config_from_file()
            self.config.update(read_config)
        else:
            sys.tracebacklimit = 0
            raise FileNotFoundError(
                f"Файл конфигурации не найден по указанному пути [{self.config_path}]"
            )

    def get_config_from_file(self):
        """Считать конфигурацию из файла.

        Returns:
            dict: Словарь с параметрами конфигурации.
        """
        _config = configparser.ConfigParser()
        _config.optionxform = str
        _config.read(self.config_path)
        return _config["defaults"]

    def init_logging(self):
        """Инициализация логгирования"""
        logging.basicConfig(
            level=self.config["LOGGING_LEVEL"],
            filename=self.config["LOG_FILE"],
            format="%(asctime)s %(levelname)s %(message)s",
            datefmt="%Y.%m.%d %H:%M:%S",
        )
        self.logger = logging.getLogger(self.__class__.__name__)

    def process_line(self, line):
        """Парсинг строки файла логов.

        Args:
            line (str): Строка лога.
        """
        self.log_strings_count += 1
        groups = self.log_line_pattern.match(line)
        self.logger.debug(f"{groups=}")
        try:
            tuples = groups.groups()

            colnames = (
                "remote_addr",
                "remote_user",
                "http_x_real_ip",
                "time_local",
                "request",
                "status",
                "body_bytes_sent",
                "http_referer",
                "http_user_agent",
                "http_x_forwarded_for",
                "http_X_REQUEST_ID",
                "http_X_RB_USER",
                "request_time",
            )

            _log = dict(zip(colnames, tuples))
            _log["status"] = int(_log["status"])
            _log["request_time"] = float(_log["request_time"])
            _log["body_bytes_sent"] = (
                lambda s: int(_log["body_bytes_sent"])
                if _log["body_bytes_sent"] != "-"
                else 0
            )
            request = _log["request"].split()
            if len(request) != 3:
                self.logger.error(f"Incorrect request [{_log['request']}]")
                self.log_strings_error += 1
                return
            url = request[1]
            request_time = _log["request_time"]
            if url in self.report_data:
                self.report_data[url]["request_times"].append(request_time)
                self.report_data[url]["time_sum"] += request_time
            else:
                self.report_data[url] = {
                    "request_times": [request_time],
                    "time_sum": request_time,
                    "url": url,
                }

            self.log_sum_time += request_time
            self.log_strings_parsed += 1
        except Exception as exc:
            msg = str(exc)
            self.logger.error(f"Ошибка парсинга строки [{line}]: {msg}", exc_info=True)
            self.log_strings_error += 1

    def parse_file(self, file_path):
        """Парсинг файла логов.

        Args:
            file_path (str): Путь к файлу логов.
        """
        self.logger.info(f"Старт обработки файла [{file_path}]")
        try:
            opener = gzip.open if file_path.endswith(".gz") else open
            for line in opener(file_path, mode="rt", errors="ignore", encoding="utf8"):
                self.process_line(line)
        except Exception as exc:
            msg = str(exc)
            self.logger.error(
                f"Ошибка парсинга файла [{file_path}]: {msg}", exc_info=True
            )
        self.logger.info("Файл успешно обработан")

    @staticmethod
    def get_report_name(file_date):
        """Определенеи имени файла отчета.

        Args:
            file_date (datetime.date): Дата файла логов.

        Returns:
            str: Имя файла отчета.
        """
        report_name = "report-" + ".".join(
            (
                str(file_date.year),
                str(file_date.month),
                str(file_date.day),
                "html",
            )
        )

        return report_name

    def get_log_file(self):
        """Отбор файла логов для парсинга"""
        file_path = None
        log_dir = self.config["LOG_DIR"]
        report_dir = self.config["REPORT_DIR"]
        log_files = {}
        try:
            for file in os.listdir(log_dir):
                self.logger.debug(f"{file=}")
                file_name = os.path.basename(file)
                self.logger.debug(f"{file_name=}")
                match_name_obj = re.match(self.log_file_name_pattern, file_name)
                is_match_name = bool(match_name_obj)
                self.logger.debug(f"{is_match_name=}")

                if is_match_name:
                    file_ext = match_name_obj.group("file_ext")

                    if file_ext not in (".gz", None):
                        continue
                    file_date_str = match_name_obj.group("file_date")
                    self.logger.debug(f"{file_date_str=}")
                    file_date = datetime.datetime.strptime(
                        file_date_str, "%Y%m%d"
                    ).date()
                    if file_date in log_files:
                        self.logger.info(
                            f"Найдено несколько файлов на 1 дату [{file_date}]"
                        )
                    log_files[file_date] = os.path.join(log_dir, file)
            self.logger.debug(f"{log_files=}")
            if not log_files:
                return
            max_date = max(log_files.keys())
            file_path = log_files.get(max_date)
            report_name = self.get_report_name(max_date)
            self.logger.debug(f"{report_name=}")
            report_path = os.path.join(report_dir, report_name)
            self.logger.debug(f"{report_path=}")
            if os.path.exists(report_path):
                return
            self.file_date = max_date
        except FileNotFoundError as exc:
            msg = str(exc)
            self.logger.error(f"Не найден путь: {msg}")
        except Exception as exc:
            self.logger.error(str(exc), exc_info=True)
        return file_path

    def calculate_report_data(self):
        """Расчет параметров отчета."""
        self.logger.info("Расчет параметров отчета")
        report_size = int(self.config["REPORT_SIZE"])
        sorted_log = sorted(
            self.report_data.items(), key=lambda x: x[1]["time_sum"], reverse=True
        )
        self.report_data = list(dict(sorted_log[:report_size]).values())
        for attrs in self.report_data:
            calculated_attrs = {}
            times = attrs["request_times"]
            time_sum = attrs["time_sum"]
            count = len(times)
            calculated_attrs["count"] = count
            calculated_attrs["count_perc"] = count / self.log_strings_count
            calculated_attrs["time_perc"] = time_sum / self.log_sum_time
            calculated_attrs["time_avg"] = mean(times)
            calculated_attrs["time_max"] = max(times)
            calculated_attrs["time_med"] = median(times)
            attrs.pop("request_times")
            attrs.update(**calculated_attrs)
            report_size -= count
        self.logger.debug(f"{self.report_data=}")
        self.logger.info("Расчет окончен")

    def generate_report(self):
        """Формирование файла отчета."""
        self.logger.info("Выгрузка отчета в файл")
        report_dir = self.config["REPORT_DIR"]
        if not os.path.exists(report_dir):
            os.mkdir(report_dir)
        report_file_name = LogAnalyzer.get_report_name(self.file_date)
        report_file_path = os.path.join(report_dir, report_file_name)
        with open("report.html", "r") as tpl:
            template = string.Template(tpl.read())
        report = template.safe_substitute(table_json=self.report_data)
        with open(report_file_path, "w", encoding="utf8") as output:
            output.write(report)
        error_rate = self.log_strings_error / self.log_strings_count
        if error_rate > float(self.config["ALLOW_ERROR_RATE"]):
            self.logger.error(f"Превышен допустимый процент ошибок [{error_rate}]")
        self.logger.info(f"Отчет выгружен в файл [{report_file_name}]")

    def run(self):
        """Запуск анализатора логов"""
        self.logger.info("Запущен анализатор логов")
        file_path = self.get_log_file()
        if file_path is None:
            self.logger.info("Отсутствуют файлы для обработки")
            return
        self.parse_file(file_path)
        self.calculate_report_data()
        self.generate_report()


def main():
    "Основная функция скрипта"
    config_path = None

    if len(sys.argv) == 1:
        pass
    else:
        if len(sys.argv) > 3:
            print("Ошибка. Слишком много параметров.")
            sys.exit(1)
        param_name = sys.argv[1]
        param_value = sys.argv[2] if len(sys.argv) == 3 else None
        if param_name == "--config" or param_name == "-c":
            config_path = param_value if param_value else config["CONFIG_PATH"]
        else:
            print(f"Ошибка. Неизвестный параметр '{param_name}'")
            sys.exit(1)

    analyzer = LogAnalyzer(config, config_path)
    try:
        analyzer.run()
    except BaseException as exc:
        analyzer.logger.error(str(exc), exc_info=True)


if __name__ == "__main__":
    main()
