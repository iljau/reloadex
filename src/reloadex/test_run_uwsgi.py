import shlex
import unittest
import os

import reloadex
from reloadex import reloader


class TestRunUwsgi(unittest.TestCase):
    def test01(self):
        # cmd = """ --uwsgi "uwsgi --http :9090 --enable-threads --master --workers 2 --wsgi-file app_flask.py" """
        cmd = """ --uwsgi "uwsgi --http :9090 --lazy-apps --enable-threads --master --workers 1 --wsgi-file app_flask.py" """

        args = shlex.split(cmd)

        working_directory, namespace = reloader.parse_args(args)

        ROOT_PATH = os.path.dirname(reloadex.__file__)
        sample_apps_directory = os.path.abspath(os.path.join(ROOT_PATH, "../../_sample_apps"))

        print("working_directory", working_directory)
        print("namespace", namespace)

        reloader._main(sample_apps_directory, namespace)