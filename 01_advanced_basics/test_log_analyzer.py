import logging
from datetime import date
from unittest import TestCase, main, mock

from log_analyzer import LogAnalyzer, config

VALID_TEST_LINE = '1.169.137.128 -  - [29/Jun/2017:03:50:23 +0300] "GET test_url HTTP/1.1" 200 1002 "-" "Configovod" "-" "1498697423-2118016444-4708-9752777" "712e90144abee9" 0.680'
INVALID_TEST_LINE = '1.202.56.176 -  - [29/Jun/2017:03:59:15 +0300] "0" 400 166 "-" "-" "-" "-" "-" 0.000'

logging.disable()


class LogAnalyzerTest(TestCase):
    def test_get_report_name(self):
        """Тест метода get_report_name."""
        test_date = date(1900, 10, 1)
        valid_name = "report-1900.10.1.html"
        generated_name = LogAnalyzer.get_report_name(test_date)
        self.assertEqual(generated_name, valid_name)

    def test_process_line_success(self):
        """Тест метода process_line. Позитивный сценарий."""
        test_analyzer = LogAnalyzer(config, None)
        test_analyzer.process_line(VALID_TEST_LINE)
        valid_dict = {
            "log_strings_count": 1,
            "log_strings_error": 0,
            "report_data": {
                "test_url": {
                    "request_times": [0.68],
                    "time_sum": 0.68,
                    "url": "test_url",
                }
            },
            "log_sum_time": 0.68,
            "log_strings_parsed": 1,
        }
        test_dict = {
            "log_strings_count": test_analyzer.log_strings_count,
            "log_strings_error": test_analyzer.log_strings_error,
            "report_data": test_analyzer.report_data,
            "log_sum_time": test_analyzer.log_sum_time,
            "log_strings_parsed": test_analyzer.log_strings_parsed,
        }
        self.assertDictEqual(valid_dict, test_dict)

    def test_process_line_error(self):
        """Тест метода process_line. Негативный сценарий."""
        test_analyzer = LogAnalyzer(config, None)
        test_analyzer.process_line(INVALID_TEST_LINE)
        valid_dict = {
            "log_strings_count": 1,
            "log_strings_error": 1,
            "report_data": {},
            "log_sum_time": 0,
            "log_strings_parsed": 0,
        }
        test_dict = {
            "log_strings_count": test_analyzer.log_strings_count,
            "log_strings_error": test_analyzer.log_strings_error,
            "report_data": test_analyzer.report_data,
            "log_sum_time": test_analyzer.log_sum_time,
            "log_strings_parsed": test_analyzer.log_strings_parsed,
        }
        self.assertDictEqual(valid_dict, test_dict)

    @mock.patch("os.listdir")
    def test_get_log_file(self, listdir_mock):
        """Тест метода get_log_file."""
        listdir_mock.return_value = [
            "nginx-access-ui.log-20170630.gz",
            "nginx-access-ui.log-20170730.gz",
            "nginx-access-ui.log-20170830.bz2",
            "nginx-access-ui.log-20170630",
            "nginx-access-ui.log",
        ]
        test_analyzer = LogAnalyzer(config, None)
        valid_file_path = "./log/nginx-access-ui.log-20170730.gz"
        file_path = test_analyzer.get_log_file()
        self.assertEqual(file_path, valid_file_path)


if __name__ == "__main__":
    main()
