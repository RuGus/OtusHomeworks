#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import os
from datetime import datetime as dt
from urllib.parse import unquote

DELIMETR = "\r\n"
DOUBLE_DELIMETR = "\r\n\r\n"
OK = 200
BAD_REQUEST = 400
FORBIDDEN = 403
NOT_FOUND = 404
INVALID_REQUEST = 422
INTERNAL_ERROR = 500
DESCRIPTIONS = {
    OK: "OK",
    BAD_REQUEST: "Bad Request",
    FORBIDDEN: "Forbidden",
    NOT_FOUND: "Not Found",
    INVALID_REQUEST: "Invalid Request",
    INTERNAL_ERROR: "Internal Server Error",
}
CONTENT_TYPE = {
    ".html": "text/html",
    ".txt": "text/html",
    ".css": "text/css",
    ".js": "text/javascript",
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".gif": "image/gif",
    ".png": "image/png",
    ".swf": "application/x-shockwave-flash",
}

LOGGING_LEVEL = logging.INFO


class SimpleResponse:
    allowed_method = ["GET", "HEAD"]
    max_size = 2048

    def __init__(self, server, root, request):
        self.root = root
        self.server = server
        self.request = request
        self.method = ""
        self.http_version = ""
        self.path = ""
        self.args = ""
        self.file_path = ""
        self.file_content = ""
        self.response_content = ""
        self.logger = None
        self.init_logging()
        self.parse_request()
        self.create_response()

    def init_logging(self):
        """Инициализация логгирования"""
        logging.basicConfig(
            level=LOGGING_LEVEL,
            format="%(asctime)s %(levelname)s %(message)s",
            datefmt="%Y.%m.%d %H:%M:%S",
        )
        self.logger = logging.getLogger(self.__class__.__name__)

    def parse_request(self):
        """Распарсить запрос"""
        self.logger.debug("Парсинг запроса")
        client_content = self.get_request_content()

        if not client_content:
            self.logger.debug("Нет данных для парсинга")
            return

        service_content, *other = client_content.split(DELIMETR)
        self.method, self.path, self.http_version = service_content.split()
        self.path = unquote(self.path.lstrip("/"))

        if "?" in self.path:
            self.path, self.args = self.path.split("?")
        self.logger.debug("Парсинг выполнен")

    def create_response(self):
        """Сформировать ответ"""
        try:
            self.prepare_file_content()
        except FileNotFoundError as err:
            self.logger.error(err)
            self.do_HEAD(NOT_FOUND)
            return

        if self.method not in self.allowed_method:
            self.logger.error(f'Не разрешенный метод "{self.method}"')
            self.do_GET(BAD_REQUEST)
            return

        if "../" in self.file_path:
            self.logger.error(f'Не разрешенный путь "{self.file_path}"')
            self.do_GET(FORBIDDEN)
            return

        self.do_HEAD(OK) if self.method == "HEAD" else self.do_GET(OK)

    def do_HEAD(self, code):
        self.response_content = (
            f"{self.http_version} {code} {DESCRIPTIONS[code]}{DELIMETR}".encode()
        )
        self.set_headers()

    def do_GET(self, code):
        self.do_HEAD(code)
        self.response_content += self.file_content

    def set_headers(self):
        """Формирование заголовков"""
        self.logger.debug("Формирование заголовков")
        headers = [
            f"Server: {self.server}",
            f'Date: {dt.now().strftime("%Y.%m.%d %H:%M:%S")}',
            f"Content-Length: {len(self.file_content)}",
            f"Content-Type: {self.get_content_type(self.file_path)}",
            "Connection: keep-alive",
        ]

        self.response_content += (
            f"{DELIMETR}".join(headers).encode() + DOUBLE_DELIMETR.encode()
        )
        self.logger.debug("Заголовки сформированы")

    def get_request_content(self):
        """Получение контента из запроса"""
        self.logger.debug("Получение контента из запроса")
        fragments = []
        while True:
            chunk = self.request.recv(self.max_size).decode("utf-8")
            fragments.append(chunk)
            if not chunk or DOUBLE_DELIMETR in chunk:
                break

        request_content = "".join(fragments)
        self.logger.debug(f"Получен контент [{request_content}]")
        return request_content.strip(DOUBLE_DELIMETR)

    def prepare_file_content(self):
        """Подготовка содержимого файла к отправке"""
        self.logger.debug(f"Подготовка содержимого для пути [{self.path}]")
        if os.path.isfile(self.path):
            self.logger.debug(f"Обнаружен путь до файла [{self.path}]")
            self.file_path = os.path.join(self.root, self.path)
        elif self.path.endswith("/") and not os.path.isdir(self.path):
            raise FileNotFoundError
        else:
            self.file_path = os.path.join(self.path, "index.html")

        with open(self.file_path, "rb") as f:
            self.file_content = f.read()
        self.logger.debug("Файл прочитан")

    def get_content_type(self, file_path):
        """Получить тип контента"""
        self.logger.debug(f"Получен контент [{file_path}]")
        file_ext = os.path.splitext(file_path)[1]
        self.logger.debug(f"Определено расширение [{file_ext}]")
        if not file_ext:
            return ""
        content_type = CONTENT_TYPE.get(file_ext, "")
        self.logger.debug(f"Определен тип контента [{content_type}]")
        return content_type
