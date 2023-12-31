#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse

from http_server import ROOT_FILE_DIR, WORKER_COUNT, SimpleWebServer

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-w",
        "--worker",
        type=int,
        help="количество потоков обработки запросов",
        default=WORKER_COUNT,
    )
    parser.add_argument(
        "-r",
        "--root",
        type=str,
        help="корневой каталог для файлов",
        default=ROOT_FILE_DIR,
    )
    args = parser.parse_args()

    server = SimpleWebServer(worker_count=args.worker, root_file_dir=args.root)
    server.server_start()
