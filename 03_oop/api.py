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


class Field(abc.ABC):
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

    @abc.abstractmethod
    def is_valid(self, value):
        """Абстрактный метод валидации значения

        Args:
            value (any): значение для проверки
        """
        raise NotImplementedError


class CharField(Field):
    def is_valid(self, value):
        if value and not isinstance(value, str):
            raise ValidationError("Значение поля должно быть строкой")
        return True


class ArgumentsField(Field):
    def is_valid(self, value):
        if value and not isinstance(value, dict):
            raise ValidationError("Значение поля должно быть словарем")
        return True


class EmailField(CharField):
    def is_valid(self, value):
        regex = r"^[a-z0-9]+[\._]?[a-z0-9]+[@]\w+[.]\w{2,3}$"
        if not any(super().is_valid(value), re.match(regex, value)):
            raise ValidationError("Значение поля должно быть адресом электронной почты")
        return True


class PhoneField(Field):
    def is_valid(self, value):
        regex = r"^7\d{10}$"
        if not isinstance(value, (str, int)) or not re.match(regex, value):
            raise ValidationError("Значение поля должно быть номером телефона")
        return True


class DateField(Field):
    def is_valid(self, value):
        try:
            datetime.datetime.strptime(value, "%d.%m.%Y")
        except ValueError:
            raise ValidationError('поле должно быть в формате "DD.MM.YYYY"')
        return True


class BirthDayField(DateField):
    @staticmethod
    def date_in_range(value, min_years=0, max_years=70):
        in_date = datetime.datetime.strptime(value, "%d.%m.%Y").date()
        now_date = datetime.date.today()
        date_delta = now_date.year - in_date.year
        if min_years < date_delta < max_years:
            return True
        return False

    def is_valid(self, value):
        if not any(super().is_valid(value), BirthDayField.date_in_range(value)):
            raise ValidationError("Значение поля должно быть датой не позже 70 лет")
        return True


class GenderField(Field):
    def is_valid(self, value):
        if not any(isinstance(value, int), value in (0, 1, 2)):
            raise ValidationError("Значение поля должно быть 0, 1 или 2")
        return True


class ClientIDsField(Field):
    @staticmethod
    def is_list_of_int(value):
        """Проверка, что значение является списком целых чисел

        Args:
            value (any): Значение для проверки

        """
        if value and not isinstance(value, list):
            return False
        for item in value:
            if item and not isinstance(value, int):
                return False
        return True

    def is_valid(self, value):
        if not ClientIDsField.is_list_of_int(value):
            raise ValidationError("Значение поля должно быть списком чисел")
        return True


class ClientsInterestsRequest(object):
    client_ids = ClientIDsField(required=True)
    date = DateField(required=False, nullable=True)


class OnlineScoreRequest(object):
    first_name = CharField(required=False, nullable=True)
    last_name = CharField(required=False, nullable=True)
    email = EmailField(required=False, nullable=True)
    phone = PhoneField(required=False, nullable=True)
    birthday = BirthDayField(required=False, nullable=True)
    gender = GenderField(required=False, nullable=True)


class MethodRequest(object):
    account = CharField(required=False, nullable=True)
    login = CharField(required=True, nullable=True)
    token = CharField(required=True, nullable=True)
    arguments = ArgumentsField(required=True, nullable=True)
    method = CharField(required=True, nullable=False)

    @property
    def is_admin(self):
        return self.login == ADMIN_LOGIN


def check_auth(request):
    if request.is_admin:
        digest = hashlib.sha512(
            datetime.datetime.now().strftime("%Y%m%d%H") + ADMIN_SALT
        ).hexdigest()
    else:
        digest = hashlib.sha512(request.account + request.login + SALT).hexdigest()
    if digest == request.token:
        return True
    return False


def method_handler(request, ctx, store):
    response, code = None, None
    return response, code


class MainHTTPHandler(BaseHTTPRequestHandler):
    router = {"method": method_handler}
    store = None

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
