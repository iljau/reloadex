import argparse
import os
import sys

from pathspec import PathSpec

from reloadex.common.utils_reloader import LaunchParams

DEFAULT_RELOADIGNORE = """
# Ignore everything ..
*
*/

# .. except *.py files
!*.py
"""


class Reloader:
    def __init__(self, platform_reloader, working_directory, argparse_args):
        self.platform_reloader = platform_reloader
        self.launch_params = LaunchParams(
            working_directory=working_directory,
            argparse_args=argparse_args,
            file_triggers_reload_fn=self.file_triggers_reload
        )

        self.spec = None
        self.reload_reloadignore()

    def start(self):
        self.platform_reloader.main(self.launch_params)

    def file_triggers_reload(self, filename_bytes):
        filename_str = filename_bytes.decode(sys.getfilesystemencoding())

        rel_filename = os.path.relpath(filename_str, self.launch_params.working_directory)
        if rel_filename == '.reloadignore':
            self.reload_reloadignore()

        triggers_reload = not self.spec.match_file(rel_filename)
        return triggers_reload

    def reload_reloadignore(self):
        try:
            # have to specify full path here, otherwise file is not found
            with open(self.launch_params.working_directory + '/.reloadignore', 'r') as fh:
                self.spec = PathSpec.from_lines('gitwildmatch', fh)
        except IOError as e:
            if e.errno == 2:
                # may happen if file is deleted and inotifyevent is triggered for that
                # print("'.reloadignore' not found. Using default spec.")
                self.spec = PathSpec.from_lines('gitwildmatch', DEFAULT_RELOADIGNORE.splitlines())
            else:
                raise


def parse_args(args=None):
    parser = get_parser()

    if len(args) == 0:
        parser.print_help(sys.stderr)
        sys.exit(1)

    argparse_args, unknown_args = parser.parse_known_args(args)
    argparse_args.cmd_params = unknown_args

    working_directory = os.getcwd()
    return working_directory, argparse_args

def get_parser():
    parser = argparse.ArgumentParser(description='Restart WSGI server on code changes')

    group = parser.add_mutually_exclusive_group()

    group.add_argument('--cmd', dest='cmd', action='store_const',
                        const=True, default=False,
                        help='execute command (default is to invoke Python module)')

    group.add_argument('--uwsgi', dest='uwsgi', action='store_const',
                        const=True, default=False,
                        help='execute uwsgi command (default is to invoke Python module)')

    return parser

def _main(working_directory, argparse_args):
    if argparse_args.uwsgi:
        from reloadex.linux import reloader_uwsgi
        platform_reloader = reloader_uwsgi
    elif sys.platform.startswith("linux"):
        from reloadex.linux import reloader_linux
        platform_reloader = reloader_linux
    elif sys.platform.startswith("win32"):
        from reloadex.windows import reloader_windows
        platform_reloader = reloader_windows
    else:
        raise NotImplementedError("unsupported platform: %s" % sys.platform)

    reloader = Reloader(platform_reloader=platform_reloader, working_directory=working_directory, argparse_args=argparse_args)
    reloader.start()


def main():
    working_directory, argparse_args = parse_args(sys.argv[1:])
    _main(working_directory, argparse_args)


if __name__ == "__main__":
    main()


