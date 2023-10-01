#!/usr/bin/env python
# -*- coding: utf-8 -*-
import collections
import glob
import gzip
import logging
import multiprocessing as mp
import os
import sys
import threading
import time
from functools import partial
from optparse import OptionParser
from queue import Empty, Queue

import appsinstalled_pb2
import memcache

NORMAL_ERR_RATE = 0.01
AppsInstalled = collections.namedtuple(
    "AppsInstalled", ["dev_type", "dev_id", "lat", "lon", "apps"]
)
config = {
    "MEMC_MAX_RETRIES": 3,
    "MEMC_TIMEOUT": 3,
    "MAX_JOB_QUEUE_SIZE": 0,
    "MAX_RESULT_QUEUE_SIZE": 0,
    "THREADS_PER_WORKER": 4,
    "MEMC_BACKOFF_FACTOR": 0.3,
    "GET_POOL_TIMEOUT": 0.1,
    "GET_JOB_TIMEOUT": 0.1,
}


def dot_rename(path):
    """Добавление префикса "." к имени файла.

    Args:
        path (str): Полный путь к файлу.
    """
    head, fn = os.path.split(path)
    # atomic in most cases
    os.rename(path, os.path.join(head, "." + fn))


def insert_appsinstalled(memc_pool, memc_client, appsinstalled, dry_run=False):
    """Запись данных в кеш.

    Args:
        memc_pool (Queue): Очередь обработки кеша
        memc_addr (str): Адрес для вставки
        appsinstalled (AppsInstalled): Данные для записи
        dry_run (bool, optional): Фланг необходимости доп. логирования.

    Returns:
        bool: Результат записи данных в кеш
    """
    ua = appsinstalled_pb2.UserApps()
    ua.lat = appsinstalled.lat
    ua.lon = appsinstalled.lon
    key = "%s:%s" % (appsinstalled.dev_type, appsinstalled.dev_id)
    ua.apps.extend(appsinstalled.apps)
    packed = ua.SerializeToString()
    try:
        if dry_run:
            value = str(ua).replace("\n", " ")
            logging.debug(f"[{memc_client}]:[{key}] -> {value}")
        else:
            try:
                memc = memc_pool.get(timeout=config["GET_POOL_TIMEOUT"])
            except Empty:
                logging.warning(f"Queue is empty [{memc_pool}]")
                memc = memc_client
            ok = False
            for retry_num in range(1, config["MEMC_MAX_RETRIES"]):
                ok = memc.set(key, packed)
                if ok:
                    break
                backoff_value = config["MEMC_BACKOFF_FACTOR"] * (2**retry_num)
                time.sleep(backoff_value)
            memc_pool.put(memc)
            return ok
    except Exception as e:
        logging.exception("Cannot write to memc %s: %s" % (memc_client, e))
        return False
    return True


def parse_appsinstalled(line):
    """Парсинг сырых данных из строки в именованый кортеж.

    Args:
        line (str): Строка с сырыми данными для парсинга

    Returns:
        AppsInstalled: Именованный кортеж с данными
    """
    line_parts = line.strip().split("\t")
    if len(line_parts) < 5:
        return
    dev_type, dev_id, lat, lon, raw_apps = line_parts
    if not dev_type or not dev_id:
        return
    try:
        apps = [int(a.strip()) for a in raw_apps.split(",")]
    except ValueError:
        apps = [int(a.strip()) for a in raw_apps.split(",") if a.isidigit()]
        logging.info("Not all user apps are digits: `%s`" % line)
    try:
        lat, lon = float(lat), float(lon)
    except ValueError:
        logging.info("Invalid geo coords: `%s`" % line)
    return AppsInstalled(dev_type, dev_id, lat, lon, apps)


def handle_insert_appsinstalled(job_queue, result_queue):
    """Обработчик задания записи в кеш

    Args:
        job_queue (Queue): Очередь с заданий
        result_queue (Queue): Очередь результатов
    """
    processed = errors = 0
    while True:
        try:
            task = job_queue.get(timeout=config["GET_JOB_TIMEOUT"])
        except Empty:
            logging.debug("Job queue is empty")
            result_queue.put((processed, errors))
            return

        memc_pool, memc_client, appsinstalled, dry_run = task
        ok = insert_appsinstalled(memc_pool, memc_client, appsinstalled, dry_run)
        if ok:
            processed += 1
        else:
            errors += 1


def get_memc_clients(device_memc):

    memc_clients = {}
    for key, value in device_memc.items():
        if value:
            memc_clients[key] = memcache.Client(
                [value],
                socket_timeout=config["MEMC_TIMEOUT"],
            )
    return memc_clients


def handle_logfile(fn, options):
    """Обработчик файла с логами

    Args:
        fn (str): Путь до файла с логами
        options (dict): Словарь с опциями обработки

    Returns:
        str: Путь до обработанного файла слогами
    """
    device_memc = {
        "idfa": options.idfa,
        "gaid": options.gaid,
        "adid": options.adid,
        "dvid": options.dvid,
    }
    memc_clients = get_memc_clients(device_memc)

    pools = collections.defaultdict(Queue)
    job_queue = Queue(maxsize=config["MAX_JOB_QUEUE_SIZE"])
    result_queue = Queue(maxsize=config["MAX_RESULT_QUEUE_SIZE"])

    workers = []
    for i in range(config["THREADS_PER_WORKER"]):
        thread = threading.Thread(
            target=handle_insert_appsinstalled,
            args=(job_queue, result_queue),
        )
        thread.daemon = True
        workers.append(thread)

    for thread in workers:
        thread.start()

    processed = errors = 0
    logging.info("Processing %s" % fn)

    try:
        with gzip.open(fn, "rt") as fd:
            for line in fd:
                line = line.strip()
                if not line:
                    continue

                appsinstalled = parse_appsinstalled(line)
                if not appsinstalled:
                    errors += 1
                    continue

                memc_addr = device_memc.get(appsinstalled.dev_type)
                if not memc_addr:
                    errors += 1
                    logging.error("Unknow device type: %s" % appsinstalled.dev_type)
                    continue
                memc_client = memc_clients.get(appsinstalled.dev_type)
                
                job_queue.put((pools[memc_addr], memc_client, appsinstalled, options.dry))

                if not all(thread.is_alive() for thread in workers):
                    break
    except Exception as exc:
        logging.error("File read error: %s" % str(exc))
        return fn

    for thread in workers:
        if thread.is_alive():
            thread.join()

    while not result_queue.empty():
        processed_per_worker, errors_per_worker = result_queue.get()
        processed += processed_per_worker
        errors += errors_per_worker

    if processed:
        err_rate = float(errors / processed)
        if err_rate < NORMAL_ERR_RATE:
            logging.info("Acceptable error rate (%s). Successfull load" % err_rate)
        else:
            logging.error(
                "High error rate (%s > %s). Failed load" % (err_rate, NORMAL_ERR_RATE)
            )

    return fn


def main(options):
    logging.info("Started cache upload process")
    num_processes = mp.cpu_count()
    logging.info(f"Multiprocessing with {num_processes=}")
    pool = mp.Pool(processes=num_processes)
    fnames = sorted(fn for fn in glob.iglob(options.pattern))
    handler = partial(handle_logfile, options=options)
    for fn in pool.imap(handler, fnames):
        dot_rename(fn)


def prototest():
    """Тест работоспособности."""
    logging.info("Start prototest")
    sample = "idfa\t1rfw452y52g2gq4g\t55.55\t42.42\t1423,43,567,3,7,23\n\
        gaid\t7rfw452y52g2gq4g\t55.55\t42.42\t7423,424"
    for line in sample.splitlines():
        dev_type, dev_id, lat, lon, raw_apps = line.strip().split("\t")
        apps = [int(a) for a in raw_apps.split(",") if a.isdigit()]
        lat, lon = float(lat), float(lon)
        ua = appsinstalled_pb2.UserApps()
        ua.lat = lat
        ua.lon = lon
        ua.apps.extend(apps)
        packed = ua.SerializeToString()
        unpacked = appsinstalled_pb2.UserApps()
        unpacked.ParseFromString(packed)
        assert ua == unpacked
    logging.info("Prototest success")


if __name__ == "__main__":
    op = OptionParser()
    op.add_option("-t", "--test", action="store_true", default=False)
    op.add_option("-l", "--log", action="store", default=None)
    op.add_option("--dry", action="store_true", default=False)
    op.add_option("--pattern", action="store", default="/data/appsinstalled/*.tsv.gz")
    op.add_option("--idfa", action="store", default="127.0.0.1:33013")
    op.add_option("--gaid", action="store", default="127.0.0.1:33014")
    op.add_option("--adid", action="store", default="127.0.0.1:33015")
    op.add_option("--dvid", action="store", default="127.0.0.1:33016")
    (opts, args) = op.parse_args()
    logging.basicConfig(
        filename=opts.log,
        level=logging.INFO if not opts.dry else logging.DEBUG,
        format="[%(asctime)s] %(levelname).1s %(message)s",
        datefmt="%Y.%m.%d %H:%M:%S",
    )
    if opts.test:
        prototest()
        sys.exit(0)

    logging.info("Memc loader started with options: %s" % opts)
    try:
        main(opts)
    except Exception as e:
        logging.exception("Unexpected error: %s" % e)
        sys.exit(1)
