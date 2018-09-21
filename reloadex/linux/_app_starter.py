import os
import signal
import sys

import atexit

from reloadex.common.utils_app_starter import get_callable
from reloadex.linux.ctypes_wrappers._eventfd import eventfd_write
from reloadex.linux.ctypes_wrappers._prctl import prctl, PR_SET_PDEATHSIG


def notify_process_inited(efd_process_started_fileno_str):
    efd_process_started_fileno = int(efd_process_started_fileno_str)
    eventfd_write(efd_process_started_fileno, 1)


# FIXME: sometimes SystemExit is raised -> we'd like to have silent exit
def signal_handler(signum, frame):
    # print("signal_handler", signum, frame)
    sys.exit(3)


def atexit_func(*args, **kwargs):
    # print("atexit_func", args, kwargs)
    pass


def main():
    # https://stackoverflow.com/questions/284325/how-to-make-child-process-die-after-parent-exits/284443#284443
    # Child can ask kernel to deliver SIGHUP (or other signal) when parent dies by specifying option PR_SET_PDEATHSIG in prctl() syscall
    prctl(PR_SET_PDEATHSIG, signal.SIGTERM, 0, 0, 0)

    # atexit: The functions registered via this module are not called when the program is killed by a signal not handled by Python
    atexit.register(atexit_func)
    signal.signal(signal.SIGTERM, signal_handler)

    # FIXME: on windows arguments are in different order
    efd_process_started_fileno_str, target_fn_str = sys.argv[1:]
    notify_process_inited(efd_process_started_fileno_str)

    # print("fake starting", target_fn_str)

    fn = get_callable(target_str=target_fn_str, folder=os.getcwd())
    fn()


if __name__ == "__main__":
    main()