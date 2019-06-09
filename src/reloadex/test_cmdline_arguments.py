import shlex
import unittest

from reloadex.reloader import parse_args


class TestCmdlineArguments(unittest.TestCase):
    def test01(self):
        cmds = [
            """ my_app.py """,
            """ my_app.py:main """,
            """ my_app:main """,
            """--cmd "python my_app.py" """,
            """--cmd python my_app.py --dummy_arg """,
            """ --cmd "uwsgi --http :9090 --enable-threads --master --workers 2 --wsgi-file app_flask.py" """,
            """ --cmd uwsgi --http :9090 --enable-threads --master --workers 2 --wsgi-file app_flask.py """,
            """ --uwsgi "uwsgi --http :9090 --enable-threads --master --workers 2 --wsgi-file app_flask.py" """,
        ]

        for cmd in cmds:
            args = shlex.split(cmd)
            print("args", args)

            working_directory, namespace = parse_args(args)
            print("namespace", namespace)