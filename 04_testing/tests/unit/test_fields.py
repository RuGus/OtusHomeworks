import functools
import unittest

from src import api


def cases(cases):
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args):
            for c in cases:
                new_args = args + (c if isinstance(c, tuple) else (c,))
                try:
                    f(*new_args)
                except AssertionError as err:
                    err_msg = f"Error in [{f.__name__}] with case [{c}]: {err}"
                    raise AssertionError(err_msg)

        return wrapper

    return decorator


class TestFields(unittest.TestCase):
    @cases(
        [
            [False, False, "something"],
            [True, False, "something"],
            [True, True, ""],
            [True, True, "something"],
            [False, True, ""],
            [False, True, "something"],
        ]
    )
    def test_char_valid(self, case):
        required, nullable, value = case
        test_field = api.CharField(required, nullable)
        test_field.__set__(test_field, value)
        self.assertEqual(value, test_field.value)

    @cases(
        [
            [False, False, ""],
            [False, False, None],
            [False, False, 1],
            [False, False, {}],
            [True, False, ""],
            [True, False, None],
            [True, False, 1],
            [True, False, []],
            [True, True, None],
            [True, True, 1],
        ]
    )
    def test_char_invalid(self, case):
        required, nullable, value = case
        test_field = api.CharField(required, nullable)
        with self.assertRaises(api.ValidationError):
            test_field.__set__(test_field, value)

    @cases(
        [
            [False, False, {"key": "value"}],
            [True, False, {"key": "value"}],
            [True, True, {"key": "value"}],
            [True, True, {}],
            [False, True, {"key": "value"}],
            [False, True, {}],
        ]
    )
    def test_argument_valid(self, case):
        required, nullable, value = case
        test_field = api.ArgumentsField(required, nullable)
        self.assertEqual(test_field.__set__(test_field, value), None)

    @cases(
        [
            [False, False, ""],
            [False, False, None],
            [False, False, 1],
            [False, False, {}],
            [True, False, ""],
            [True, False, "1"],
            [True, False, None],
            [True, False, 1],
            [True, False, {}],
            [True, True, None],
            [True, True, 1],
            [True, True, "1"],
        ]
    )
    def test_argument_invalid(self, case):
        required, nullable, value = case
        test_field = api.ArgumentsField(required, nullable)
        with self.assertRaises(api.ValidationError):
            test_field.__set__(test_field, value)

    @cases(
        [
            [False, False, "something@bk.ru"],
            [True, False, "somethi@bk.ru"],
            [True, True, ""],
            [True, True, "somethi@bk.ru"],
            [False, True, ""],
            [False, True, "someth@bk.ru"],
        ]
    )
    def test_email_valid(self, case):
        required, nullable, value = case
        test_field = api.EmailField(required, nullable)
        test_field.__set__(test_field, value)
        self.assertEqual(value, test_field.value)

    @cases(
        [
            [False, False, ""],
            [False, False, "something"],
            [False, False, None],
            [False, False, 1],
            [False, False, {}],
            [True, False, ""],
            [True, False, "something"],
            [True, False, None],
            [True, False, 1],
            [True, False, []],
            [False, True, "something"],
            [True, True, None],
            [True, True, "something"],
            [True, True, 1],
        ]
    )
    def test_email_invalid(self, case):
        required, nullable, value = case
        test_field = api.EmailField(required, nullable)
        with self.assertRaises(api.ValidationError):
            test_field.__set__(test_field, value)

    @cases(
        [
            [False, False, "71234567890"],
            [False, False, 71234567890],
            [True, False, "71234567890"],
            [True, False, 71234567890],
            [True, True, "71234567890"],
            [True, True, 71234567890],
            [False, True, None],
            [False, True, "71234567890"],
            [False, True, 71234567890],
        ]
    )
    def test_phone_valid(self, case):
        required, nullable, value = case
        test_field = api.PhoneField(required, nullable)
        test_field.__set__(test_field, value)
        self.assertEqual(value, test_field.value)

    @cases(
        [
            [False, False, "81234567890"],
            [False, False, ""],
            [False, False, None],
            [False, False, 1234567890],
            [False, False, {}],
            [False, False, {"key": "value"}],
            [True, False, "81234567890"],
            [True, False, ""],
            [True, False, None],
            [True, False, 1234567890],
            [True, False, {}],
            [True, False, {"key": "value"}],
            [True, True, None],
            [True, True, 81234567890],
            [True, True, {"key": "value"}],
        ]
    )
    def test_phone_invalid(self, case):
        required, nullable, value = case
        test_field = api.PhoneField(required, nullable)
        with self.assertRaises(api.ValidationError):
            test_field.__set__(test_field, value)

    @cases(
        [
            [False, False, "10.10.2022"],
            [True, False, "10.10.2023"],
            [True, True, ""],
            [True, True, "10.10.2024"],
            [False, True, ""],
            [False, True, None],
            [False, True, "10.10.2025"],
        ]
    )
    def test_date_valid(self, case):
        required, nullable, value = case
        test_field = api.DateField(required, nullable)
        test_field.__set__(test_field, value)
        self.assertEqual(value, test_field.value)

    @cases(
        [
            [False, False, "18/05/1999"],
            [False, False, None],
            [False, False, ""],
            [True, False, "10-12-2023"],
            [True, False, ""],
            [True, False, "2021"],
            [True, True, "10.2021"],
            [False, True, "01.01..2020"],
        ]
    )
    def test_date_invalid(self, case):
        required, nullable, value = case
        test_field = api.DateField(required, nullable)
        with self.assertRaises(api.ValidationError):
            test_field.__set__(test_field, value)

    @cases(
        [
            [False, False, "01.01.2020"],
            [True, False, "01.01.2020"],
            [True, True, ""],
            [True, True, "01.01.2020"],
            [False, True, ""],
            [False, True, None],
            [False, True, "01.01.2020"],
        ]
    )
    def test_bdate_valid(self, case):
        required, nullable, value = case
        test_field = api.BirthDayField(required, nullable)
        test_field.__set__(test_field, value)
        self.assertEqual(value, test_field.value)

    @cases(
        [
            [False, False, "18/05/1999"],
            [False, False, "33.10.1999"],
            [False, False, None],
            [False, False, ""],
            [True, False, "11-11-2023"],
            [True, False, "09.08.1951"],
            [True, False, ""],
            [True, False, "2022"],
            [True, True, "10.2024"],
            [True, True, "09.08.1951"],
            [False, True, "09.08.1951"],
            [False, True, "09.08.1951"],
        ]
    )
    def test_birth_date_invalid(self, case):
        required, nullable, value = case
        test_field = api.BirthDayField(required, nullable)
        with self.assertRaises(api.ValidationError):
            test_field.__set__(test_field, value)

    @cases(
        [
            [False, False, 1],
            [True, False, 2],
            [True, True, 0],
            [True, True, ""],
            [False, True, 1],
            [False, True, ""],
            [False, True, None],
        ]
    )
    def test_gender_valid(self, case):
        required, nullable, value = case
        test_field = api.GenderField(required, nullable)
        test_field.__set__(test_field, value)
        self.assertEqual(value, test_field.value)

    @cases(
        [
            [False, False, ""],
            [False, False, -1],
            [False, False, None],
            [False, False, "no man"],
            [True, False, ""],
            [True, False, -1],
            [True, False, None],
            [True, False, "alien"],
            [True, True, -1],
            [True, True, None],
            [True, True, "alien"],
            [False, True, -1],
            [False, True, "alien"],
        ]
    )
    def test_gender_invalid(self, case):
        required, nullable, value = case
        test_field = api.GenderField(required, nullable)
        with self.assertRaises(api.ValidationError):
            test_field.__set__(test_field, value)

    @cases(
        [
            [False, False, [1]],
            [True, False, [1, 2]],
            [True, True, [1, 2]],
            [False, True, [1, 2]],
            [False, True, []],
        ]
    )
    def test_id_valid(self, case):
        required, nullable, value = case
        test_field = api.ClientIDsField(required, nullable)
        test_field.__set__(test_field, value)
        self.assertEqual(value, test_field.value)

    @cases(
        [
            [False, False, "18/05/1999"],
            [False, False, None],
            [False, False, 123],
            [True, False, "18/05/1999"],
            [True, False, None],
            [True, False, 123],
            [True, True, "18/05/1999"],
            [True, True, None],
            [True, True, 123],
            [False, True, "18/05/1999"],
            [False, True, 123],
        ]
    )
    def test_id_invalid(self, case):
        required, nullable, value = case
        test_field = api.ClientIDsField(required, nullable)
        with self.assertRaises(api.ValidationError):
            test_field.__set__(test_field, value)


if __name__ == "__main__":
    unittest.main()
