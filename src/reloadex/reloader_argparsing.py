
import argparse
import sys
import shlex


def test_argparse():
    # start possibilities:

    parser = get_parser()
    # 1) reloadex app.py -> invoke python (same python as reloadex)
    args = parser.parse_args(['app.py'])
    print(args)
    # 2.1) reloadex app.py:main -> invoke main function in file
    args = parser.parse_args(['app:main'])
    print(args)
    # 3.1) reloadex --cmd "gunicorn app:app" -> invoke cmd
    args = parser.parse_args(['--cmd', "gunicorn app:app"])
    # TODO: will need to use shlex split here
    print(args)
    if len(args.cmd_params) == 1:
        res = shlex.split(args.cmd_params[0])
        print("res", res)
    # 3.2) reloadex --cmd gunicorn app:main -> invoke cmd, passing all arguments
    args = parser.parse_args(['--cmd', "gunicorn", "app:app"])
    print(args)

def get_parser():
    parser = argparse.ArgumentParser(description='Restart WSGI server on code changes')

    parser.add_argument('--cmd', dest='cmd', action='store_const',
                        const=True, default=False,
                        help='execute command (default is to invoke Python module)')

    parser.add_argument('cmd_params', metavar='args', type=str, nargs='+', help="command arguments for reloader")
    return parser


def main():
    parser = get_parser()

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    args = parser.parse_args()

if __name__ == "__main__":
    # main()
    test_argparse()