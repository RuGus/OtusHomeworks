#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import socket
import threading
from socket import AF_INET, SO_REUSEADDR, SOCK_STREAM, SOL_SOCKET

from http_response import SimpleResponse

# Default server config
HOST = "localhost"
PORT = 8080
SOCKET_TIMEOUT = 5
RECONNECT_DELAY = 3
RECONNECT_MAX_ATTEMPTS = 3
ALLOW_REUSE_ADDRESS = True
WORKER_COUNT = 1
ROOT_FILE_DIR = ""
LOGGING_LEVEL = logging.INFO


class SimpleWebServer:
    _socket = None

    def __init__(
        self,
        host=HOST,
        port=PORT,
        socket_timeout=SOCKET_TIMEOUT,
        reconnect_delay=RECONNECT_DELAY,
        reconnect_max_attempts=RECONNECT_MAX_ATTEMPTS,
        allow_reuse_address=ALLOW_REUSE_ADDRESS,
        worker_count=WORKER_COUNT,
        root_file_dir=ROOT_FILE_DIR,
    ):
        self.host = host
        self.port = port
        self.socket_timeout = socket_timeout
        self.reconnect_delay = reconnect_delay
        self.reconnect_max_attempts = reconnect_max_attempts
        self.allow_reuse_address = allow_reuse_address
        self.worker_count = worker_count
        self.root_file_dir = root_file_dir
        self.logger = None
        self.init_logging()
        self.server = None

    def init_logging(self):
        """Инициализация логгирования"""
        logging.basicConfig(
            level=LOGGING_LEVEL,
            format="%(asctime)s %(levelname)s %(message)s",
            datefmt="%Y.%m.%d %H:%M:%S",
        )
        self.logger = logging.getLogger(self.__class__.__name__)

    def server_bind(self):
        self.logger.info("Привязка сервера к хосту:порту")
        if self.allow_reuse_address:
            self._socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        self._socket.bind((self.host, self.port))
        self.server = self._socket.getsockname()
        self.logger.info(f"Сервер привязан к [{self.host}:{self.port}]")

    def create_socket(self):
        self.logger.info("Создание сокета")
        self._socket = socket.socket(AF_INET, SOCK_STREAM)
        self.logger.info("Сокет создан")

    def init_socket_listeners(self):
        self.logger.info("Запуск обработчиков на сокете")
        self._socket.listen(self.worker_count)
        self.logger.info(f"На сокете запущено {self.worker_count} обработчиков")

    def handle_client_request(self, client_request):
        self.logger.debug(f"Обработка запроса: [{str(client_request)}]")
        response = SimpleResponse(self.server, self.root_file_dir, client_request)
        client_request.send(response.response_content)
        client_request.close()

    def server_start(self):
        self.create_socket()
        self.server_bind()
        self.init_socket_listeners()

        while True:
            client_request, address = self._socket.accept()
            self.logger.debug(f"Входящее соединение [{address[0]}:{address[1]}]")
            client_handler = threading.Thread(
                target=self.handle_client_request,
                args=(client_request,),
            )
            client_handler.start()
