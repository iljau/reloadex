import shlex
import unittest
import os

import reloadex
from reloadex import reloader


class TestRunLinux(unittest.TestCase):
    def test01(self):
        cmd = """ --cmd "python app_flask.py" """

        args = shlex.split(cmd)

        working_directory, namespace = reloader.parse_args(args)

        ROOT_PATH = os.path.dirname(reloadex.__file__)
        sample_apps_directory = os.path.abspath(os.path.join(ROOT_PATH, "../../_sample_apps"))

        print("working_directory", working_directory)
        print("namespace", namespace)

        reloader._main(sample_apps_directory, namespace)