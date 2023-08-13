#!/usr/bin/env python
# -*- coding: utf-8 -*-

import abc
import datetime
import hashlib
import json
import logging
import re
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from optparse import OptionParser

from scoring import get_interests, get_score
from store import Storage, RedisStorage

SALT = "Otus"
ADMIN_LOGIN = "admin"
ADMIN_SALT = "42"
OK = 200
BAD_REQUEST = 400
FORBIDDEN = 403
NOT_FOUND = 404
INVALID_REQUEST = 422
INTERNAL_ERROR = 500
ERRORS = {
    BAD_REQUEST: "Bad Request",
    FORBIDDEN: "Forbidden",
    NOT_FOUND: "Not Found",
    INVALID_REQUEST: "Invalid Request",
    INTERNAL_ERROR: "Internal Server Error",
}
UNKNOWN = 0
MALE = 1
FEMALE = 2
GENDERS = {
    UNKNOWN: "unknown",
    MALE: "male",
    FEMALE: "female",
}


class ValidationError(ValueError):
    pass


# --------- Классы полей
class Field(abc.ABC):
    """Базовый класс поля данных"""

    empty_values = (None, "", [], (), {})

    def __init__(self, required=False, nullable=False):
        self.required = required
        self.nullable = nullable

    def __set__(self, obj, value):
        if value in self.empty_values:
            self.base_validation(value)
        elif self.is_valid(value):
            self.value = value

    def __get__(self, obj, objtype=None):
        return self.value

    def base_validation(self, value):
        """Базовая проверка на обязательность и заполненность значения

        Args:
            value (any): значение для проверки
        """
        if value is None and self.required:
            raise ValidationError("Поле обязательно для заполнения")
        if value in self.empty_values and not self.nullable:
            raise ValidationError("Поле не может быть пустым")
        self.value = value

    @abc.abstractmethod
    def is_valid(self, value):
        """Абстрактный метод валидации значения

        Args:
            value (any): значение для проверки
        """
        raise NotImplementedError


class CharField(Field):
    """Строковое поле"""

    def is_valid(self, value):
        if value and not isinstance(value, str):
            raise ValidationError("Значение поля должно быть строкой")
        return True


class ArgumentsField(Field):
    """Поле со словарем аргументов"""

    def is_valid(self, value):
        if value and not isinstance(value, dict):
            raise ValidationError("Значение поля должно быть словарем")
        return True


class EmailField(CharField):
    """Поле для адреса электронной почты"""

    def is_valid(self, value):
        regex = r"^[a-z0-9]+[\._]?[a-z0-9]+[@]\w+[.]\w{2,3}$"
        if not super().is_valid(value) or not re.match(regex, value):
            raise ValidationError("Значение поля должно быть адресом электронной почты")
        return True


class PhoneField(Field):
    """Поле для номера телефона в формате 71234567890"""

    def is_valid(self, value):
        regex = r"^7\d{10}$"
        if not isinstance(value, (str, int)) or not re.match(regex, str(value)):
            raise ValidationError("Значение поля должно быть номером телефона")
        return True


class DateField(Field):
    """Поле даты"""

    def is_valid(self, value):
        try:
            datetime.datetime.strptime(value, "%d.%m.%Y")
        except ValueError:
            raise ValidationError('поле должно быть в формате "DD.MM.YYYY"')
        return True


class BirthDayField(DateField):
    """Поле даты рождения. Не старше 70 лет."""

    @staticmethod
    def date_no_more_years(value, max_years=70):
        in_date = datetime.datetime.strptime(value, "%d.%m.%Y").date()
        now_date = datetime.date.today()
        date_delta = now_date.year - in_date.year
        if date_delta < max_years:
            return True
        return False

    def is_valid(self, value):
        if not super().is_valid(value) or not BirthDayField.date_no_more_years(value):
            raise ValidationError("Значение поля должно быть датой не позже 70 лет")
        return True


class GenderField(Field):
    """Поле для указаняи пола. 0-Ж, 1-М, 2-Иное"""

    def is_valid(self, value):
        if not isinstance(value, int) or value not in (0, 1, 2):
            raise ValidationError("Значение поля должно быть 0, 1 или 2")
        return True


class ClientIDsField(Field):
    """Список ИД клиентов"""

    @staticmethod
    def is_list_of_int(value):
        """Проверка, что значение является списком целых чисел

        Args:
            value (any): Значение для проверки

        """
        if not isinstance(value, list):
            return False
        for item in value:
            if item and not isinstance(item, int):
                return False
        return True

    def is_valid(self, value):
        if not ClientIDsField.is_list_of_int(value):
            raise ValidationError("Значение поля должно быть списком чисел")
        return True


# --------- Классы запросов
class RequestMeta(type):
    """Метакласс для запросов"""

    def __new__(mcs, name, bases, attrs):
        fields = {}
        for key, value in list(attrs.items()):
            if isinstance(value, Field):
                fields[key] = attrs.pop(key)
        attrs["fields"] = fields
        return super().__new__(mcs, name, bases, attrs)


class Request(metaclass=RequestMeta):
    """Класс запросов"""

    def __init__(self, request_fields=None):
        self.request_fields = request_fields
        self.err_msg = ""

    def __getattr__(self, item):
        return self.request_fields.get(item) or ""

    def is_valid(self):
        """Проверка валидности полей запроса"""
        return all(
            self.field_is_correct(field_name, field_obj)
            for field_name, field_obj in self.fields.items()
        )

    def field_is_correct(self, field_name, field_obj):
        """Проверка валидности поля запроса

        Args:
            field_name (str): Наименование поля в запросе.
            field_obj (object): Объект поля.

        Returns:
            bool: Результат проврки валидности.
        """
        value = self.request_fields.get(field_name)
        try:
            if value in field_obj.empty_values:
                field_obj.base_validation(value)
            else:
                field_obj.is_valid(value)
            return True
        except ValidationError as err:
            msg = f'Поле "{field_name}" со значением "{value}", не валидно({err})\n'
            self.err_msg += msg
            logging.error(msg)
            return False


class ClientsInterestsRequest(Request):
    """Класс запроса clients_interests"""

    client_ids = ClientIDsField(required=True)
    date = DateField(required=False, nullable=True)

    def set_context(self, ctx):
        """Добавление в контекст количества ИД клиентов"""
        ctx["nclients"] = len(self.client_ids)


class OnlineScoreRequest(Request):
    """Класс запроса online_score"""

    phone = PhoneField(required=False, nullable=True)
    email = EmailField(required=False, nullable=True)
    first_name = CharField(required=False, nullable=True)
    last_name = CharField(required=False, nullable=True)
    birthday = BirthDayField(required=False, nullable=True)
    gender = GenderField(required=False, nullable=True)

    def is_valid(self):
        return super().is_valid() and self.valid_required_pairs()

    def set_context(self, ctx):
        """Добавление в контекст полей запроса"""
        has = [
            field for field in self.fields if self.request_fields.get(field) is not None
        ]
        logging.info(f"Получены поля {has}")
        ctx["has"] = has

    def valid_required_pairs(self):
        """Проверка наличия обязательных пар параметров"""
        for field1, field2 in [
            ("phone", "email"),
            ("first_name", "last_name"),
            ("gender", "birthday"),
        ]:
            if all(
                (
                    self.request_fields.get(field1) is not None,
                    self.request_fields.get(field2) is not None,
                )
            ):
                return True

        self.err_msg += f"Парные поля не валидны\n"


class MethodRequest(Request):
    """Класс запроса метода"""

    account = CharField(required=False, nullable=True)
    login = CharField(required=True, nullable=True)
    method = CharField(required=True, nullable=False)
    token = CharField(required=True, nullable=True)
    arguments = ArgumentsField(required=True, nullable=True)

    @property
    def is_admin(self):
        """Признак, что запрос выполняет админ"""
        return self.login == ADMIN_LOGIN


def check_auth(request):
    if request.is_admin:
        digest = hashlib.sha512(
            (datetime.datetime.now().strftime("%Y%m%d%H") + ADMIN_SALT).encode()
        ).hexdigest()
    else:
        digest = hashlib.sha512(
            (request.account + request.login + SALT).encode()
        ).hexdigest()
    if digest == request.token:
        return True
    return False


def online_score_handler(request, store):
    birthday = datetime.datetime.strptime(request.birthday, "%d.%m.%Y") if request.birthday else None
    return {
        "score": get_score(
            store=store,
            phone=request.phone,
            email=request.email,
            birthday=birthday,
            gender=request.gender,
            first_name=request.first_name,
            last_name=request.last_name,
        )
    }, OK


def clients_interests_handler(request, store):
    return {cid: get_interests(store, cid) for cid in request.client_ids}, OK


def method_handler(request, ctx, store):
    requests = {
        "online_score": OnlineScoreRequest,
        "clients_interests": ClientsInterestsRequest,
    }

    methods = {
        "online_score": online_score_handler,
        "clients_interests": clients_interests_handler,
    }

    body, headers = request["body"], request["headers"]
    mr = MethodRequest(body)
    if not mr.is_valid():
        return mr.err_msg, INVALID_REQUEST

    if not check_auth(mr):
        logging.info("Bad auth")
        return ERRORS[FORBIDDEN], FORBIDDEN

    request = requests[body["method"]](request_fields=body["arguments"])
    method = methods[body["method"]]

    if not request.is_valid():
        return request.err_msg, INVALID_REQUEST

    if mr.is_admin:
        return {"score": 42}, OK

    request.set_context(ctx)
    return method(request, store)


class MainHTTPHandler(BaseHTTPRequestHandler):
    router = {"method": method_handler}
    store = Storage(RedisStorage())

    def get_request_id(self, headers):
        return headers.get("HTTP_X_REQUEST_ID", uuid.uuid4().hex)

    def do_POST(self):
        response, code = {}, OK
        context = {"request_id": self.get_request_id(self.headers)}
        request = None
        try:
            data_string = self.rfile.read(int(self.headers["Content-Length"]))
            request = json.loads(data_string)
        except:
            code = BAD_REQUEST

        if request:
            path = self.path.strip("/")
            logging.info("%s: %s %s" % (self.path, data_string, context["request_id"]))
            if path in self.router:
                try:
                    response, code = self.router[path](
                        {"body": request, "headers": self.headers}, context, self.store
                    )
                except Exception as exc:
                    logging.exception("Unexpected error: %s" % exc)
                    code = INTERNAL_ERROR
            else:
                code = NOT_FOUND

        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        if code not in ERRORS:
            r = {"response": response, "code": code}
        else:
            r = {"error": response or ERRORS.get(code, "Unknown Error"), "code": code}
        context.update(r)
        logging.info(context)
        self.wfile.write(json.dumps(r))
        return


if __name__ == "__main__":
    op = OptionParser()
    op.add_option("-p", "--port", action="store", type=int, default=8080)
    op.add_option("-l", "--log", action="store", default=None)
    (opts, args) = op.parse_args()
    logging.basicConfig(
        filename=opts.log,
        level=logging.INFO,
        format="[%(asctime)s] %(levelname).1s %(message)s",
        datefmt="%Y.%m.%d %H:%M:%S",
    )
    server = HTTPServer(("localhost", opts.port), MainHTTPHandler)
    logging.info("Starting server at %s" % opts.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()
