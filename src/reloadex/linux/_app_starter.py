import _thread
import logging
import os
import select
import signal
import sys

import atexit
import threading

from reloadex.common.utils_app_starter import get_callable
from reloadex.linux.ctypes_wrappers._eventfd import eventfd_write, eventfd, EFD_CLOEXEC, EFD_NONBLOCK, eventfd_read
from reloadex.linux.ctypes_wrappers._prctl import prctl, PR_SET_PDEATHSIG
from reloadex.linux.ctypes_wrappers._signalfd import sigemptyset, sigset_t, sigaddset, sigprocmask, signalfd_read, \
    SFD_CLOEXEC, SFD_NONBLOCK, signalfd, sigfillset


logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())


def atexit_func(*args, **kwargs):
    # print("app_starter: atexit_func", args, kwargs)
    pass

###
###


def setup_signalfd_parent():
    mask = sigset_t()
    sigemptyset(mask)
    sigaddset(mask, signal.SIGUSR1)

    # Block signals so that they aren't handled according to their default dispositions
    sigprocmask(signal.SIG_BLOCK, mask, None)

    signal_fd = signalfd(-1, mask, SFD_CLOEXEC|SFD_NONBLOCK)
    return signal_fd


def wait_for_termination(signal_fd, efd_child_terminated, pid):
    """
    wait for SIGINT using epoll
    """

    epoll_events = select.epoll()
    epoll_events.register(signal_fd, select.EPOLLIN)  # read
    epoll_events.register(efd_child_terminated, select.EPOLLIN)

    signal_received = False
    while True:
        if signal_received:
            logging.debug("~~~ got signal, returning")
            return

        events = epoll_events.poll()

        for fileno, event in events:
            if fileno == signal_fd and event == select.EPOLLIN:
                logging.debug("~~~ reading signal")
                # we need to handle signal in any case
                fdsi = signalfd_read(fileno)
                signal_received = True

                signo = fdsi.ssi_signo

                signame = signal.Signals(signo).name
                logging.debug("got:sig %s %s" % (signo, signame))
                assert signo == signal.SIGUSR1

                # fixme: simulate + handle exception
                logging.debug("killing")
                try:
                    os.kill(pid, signal.SIGINT)
                    logging.debug("KILLED CHILD")
                except ProcessLookupError as e:
                    if e.errno == 3:
                        # ProcessLookupError: [Errno 3] No such process
                        pass
                    else:
                        raise
                continue
            elif fileno == efd_child_terminated and event == select.EPOLLIN:
                # just return
                logging.debug("child was terminated")
                eventfd_read(efd_child_terminated)
                continue
            else:
                raise Exception("should not happen")

###
###


def main():
    original_sigint_handler = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    # FIXME: on windows arguments are in different order
    #efd_process_started_fileno_str, target_fn_str = sys.argv[1:]
    target_fn_str, = sys.argv[1:]

    pid = os.fork()
    if pid == 0:
        # child

        # ask kernel to deliver SIGHUP (or other signal) when parent dies (_app_starter main)
        prctl(PR_SET_PDEATHSIG, signal.SIGINT, 0, 0, 0)

        signal.signal(signal.SIGINT, original_sigint_handler)


        do_finally = True

        try:
            fn = get_callable(target_str=target_fn_str, folder=os.getcwd())
            fn()
        except (KeyboardInterrupt, SystemExit) as e:
            do_finally = True
        except:
            do_finally = False
            raise
        finally:
            if do_finally:
                signal.signal(signal.SIGINT, signal.SIG_IGN)
                _thread.exit()
    else:
        # parent

        # ask kernel to deliver SIGHUP (or other signal) when parent dies (reloader)
        prctl(PR_SET_PDEATHSIG, signal.SIGUSR1, 0, 0, 0)

        signal_fd = setup_signalfd_parent()

        # atexit: The functions registered via this module are not called when the program is killed by a signal not handled by Python
        atexit.register(atexit_func)

        efd_child_terminated = eventfd(0, flags=EFD_CLOEXEC | EFD_NONBLOCK)

        def wait_for_pid():
            os.waitpid(pid, 0)
            # os.wait()
            eventfd_write(efd_child_terminated, 1)

        t_wait_for_pid = threading.Thread(target=wait_for_pid)
        t_wait_for_pid.start()

        wait_for_termination(signal_fd, efd_child_terminated, pid)

        logging.debug("joining t_wait_for_pid")
        t_wait_for_pid.join()

        logging.debug("parent done")
        sys.exit(6)


if __name__ == "__main__":
    main()