import ctypes
import os
import select
import signal
import threading
import sys
import logging

from ctypes import c_int, byref, create_string_buffer
from timeit import default_timer

from reloadex.common.utils_reloader import LaunchParams
from reloadex.linux.ctypes_wrappers._eventfd import eventfd, EFD_CLOEXEC, EFD_NONBLOCK, eventfd_write, eventfd_read
from reloadex.linux.ctypes_wrappers._inotify import inotify_init1, IN_CLOEXEC, IN_NONBLOCK, inotify_add_watch, IN_ALL_EVENTS, \
    IN_ACCESS, IN_CLOSE, IN_OPEN, inotify_read, IN_CREATE, IN_ISDIR, IN_IGNORED, IN_UNMOUNT, IN_Q_OVERFLOW
from reloadex.linux.ctypes_wrappers._posix_spawn import (
    posix_spawnattr_t, posix_spawnattr_init, posix_spawnattr_setflags,
    POSIX_SPAWN_USEVFORK,
    create_char_array,
    posix_spawn,
    posix_spawnattr_destroy)
from reloadex.linux.ctypes_wrappers._timerfd import CLOCK_MONOTONIC, TFD_CLOEXEC, TFD_NONBLOCK, timerfd_create, itimerspec, \
    timerfd_settime, timerfd_read

import reloadex.linux._app_starter


logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())

##

efd_stop_reloader = None

##

def set_do_start_timer(timerfd_fd, after_ms=None):
    # set timer to launch after 50ms
    spec = itimerspec()
    spec.it_interval.tv_sec = 0
    spec.it_interval.tv_nsec = 0
    spec.it_value.tv_sec = 0

    if after_ms is not None:
        spec.it_value.tv_nsec = int(after_ms * 1000 * 1000)  # 50ms = 0.05 s
    else:
        spec.it_value.tv_nsec = 1 # immediately

    timerfd_settime(timerfd_fd, 0, ctypes.pointer(spec), None)


def disarm_do_start_timer(timerfd_fd):
    # set timer to launch after 50ms
    spec = itimerspec()
    spec.it_interval.tv_sec = 0
    spec.it_interval.tv_nsec = 0
    spec.it_value.tv_sec = 0
    spec.it_value.tv_nsec = 0


    timerfd_settime(timerfd_fd, 0, ctypes.pointer(spec), None)

class _SpawnedProcess:
    def __init__(self, process_args):
        self.process_args = process_args

        self.pid = None
        self.attr = None

        self.cleanup_lock = threading.Lock()

    def start(self):
        attr = self.attr = posix_spawnattr_t()
        psret = posix_spawnattr_init(attr)
        assert psret == 0, "psret = %s" % psret

        psret = posix_spawnattr_setflags(attr, POSIX_SPAWN_USEVFORK)
        assert psret == 0, "psret = %s" % psret

        ##

        argv = create_char_array(self.process_args)

        _env = []
        for key, value in os.environ.items():
            _env.append("%s=%s" % (key, value))
        envp = create_char_array(_env)

        path = create_string_buffer(self.process_args[0].encode("utf-8"))

        c_pid = c_int()
        psret = posix_spawn(
            byref(c_pid),
            path,
            None,  # __file_actions
            attr,
            argv,
            envp
        )
        assert psret == 0, "psret = %s" % psret

        ##

        # TODO: posix_spawnattr_destroy? after process exit?
        pid = c_pid.value
        self.pid = pid
        return pid

    def _cleanup(self):
        with self.cleanup_lock:
            # FIXME: weakref callback to auto-invoke
            if self.attr is not None:
                logging.debug("_SpawnedProcess:_cleanup:destroying spawnattr")
                psret = posix_spawnattr_destroy(self.attr)
                assert psret == 0, "psret = %s" % psret
                self.attr = None

    def stop(self):
        self._cleanup()

        if self.pid is not None:
            try:
                os.kill(self.pid, signal.SIGTERM)
                self.pid = None
            except ProcessLookupError as e:
                if e.errno == 3:
                    # ProcessLookupError: [Errno 3] No such process
                    logger.debug("terminate_process: process already terminated")
                else:
                    raise e
        else:
            logger.debug("terminate_process: pid is None")


# FIXME: efd_process_started should be visible per launched app
# FIXME: rename: not strictly process handles
class ProcessHandles:
    spawned_process: _SpawnedProcess

    def __init__(self, launch_params: LaunchParams):
        self.launch_params = launch_params

        self.spawned_process = None

        # handles

        self.efd_process_started = eventfd(0, flags=EFD_NONBLOCK)
        self.efd_process_terminated = eventfd(0, flags=EFD_CLOEXEC|EFD_NONBLOCK)

        self.efd_do_terminate_app = eventfd(0, flags=EFD_CLOEXEC | EFD_NONBLOCK)

        self.tfd_do_start_app = timerfd_create(CLOCK_MONOTONIC, TFD_CLOEXEC | TFD_NONBLOCK)



class AppRunnerThread(threading.Thread):
    def set_process_handles(self, process_handles: ProcessHandles):
        self.process_handles = process_handles

    def run(self):
        app_starter_path = reloadex.linux._app_starter.__file__

        # -u: Force the stdout and stderr streams to be unbuffered. See also PYTHONUNBUFFERED.
        # -B: don't try to write .pyc files on the import of source modules. See also PYTHONDONTWRITEBYTECODE.
        _args = [sys.executable, "-u", "-B", app_starter_path,
                 str(self.process_handles.efd_process_started), self.process_handles.launch_params.target_fn_str]

        spawned_process = self.process_handles.spawned_process = _SpawnedProcess(_args)
        pid = spawned_process.start()


        # http://code.activestate.com/recipes/578022-wait-for-pid-and-check-for-pid-existance-posix/
        # FIXME: process may already be killed

        pid, status = os.waitpid(pid, 0)

        # FIXME: cleanup may be already be happened
        spawned_process._cleanup()
        eventfd_write(self.process_handles.efd_process_terminated, 1)

        if os.WIFSIGNALED(status):
            # process exited due to a signal; return the integer of that signal
            signalcode = os.WTERMSIG(status)
            logging.debug("pid=%s: Terminated with signal %s:%s " % (pid, signalcode, signal.Signals(signalcode).name))
        elif os.WIFEXITED(status):
            # process exited using exit(2) system call; return the
            # integer exit(2) system call has been called with
            exitcode = os.WEXITSTATUS(status)
            if exitcode != 0:
                logging.debug("pid=%s: Exit code: %s" % (pid, exitcode))
        else:
            # should never happen
            raise RuntimeError("unknown process exit status")

# FIXME: not sure we need app monitoring thread -> or do we need it?
'''
class AppMonitoringThread(threading.Thread):
    def set_process_handles(self, process_handles: ProcessHandles):
        self.process_handles = process_handles

    def run(self):
        epoll_events = select.epoll()
        epoll_events.register(self.process_handles.efd_process_started, select.EPOLLIN)  # read
        epoll_events.register(self.process_handles.efd_process_terminated, select.EPOLLIN)  # read
        epoll_events.register(efd_stop_reloader, select.EPOLLIN)  # read

        while True:
            print("AppMonitoringThread:waiting for events")
            events = epoll_events.poll()

            for fileno, event in events:
                if fileno == self.process_handles.efd_process_started and event == select.EPOLLIN:
                    logger.debug("AppMonitoringThread:process_started")
                    eventfd_read(fileno)
                elif fileno == self.process_handles.efd_process_terminated and event == select.EPOLLIN:
                    logger.debug("AppMonitoringThread:process_terminated")
                    eventfd_read(fileno)
                elif fileno == efd_stop_reloader and event == select.EPOLLIN:
                    logger.debug("AppMonitoringThread:stop_reloader")
                    return
                else:
                    raise Exception("should not happen")
'''

class AppRelaunchingThread(threading.Thread):
    def set_process_handles(self, process_handles: ProcessHandles):
        self.process_handles = process_handles

    def run(self):
        epoll_events_start = select.epoll()
        epoll_events_start.register(efd_stop_reloader, select.EPOLLIN)  # read
        epoll_events_start.register(self.process_handles.tfd_do_start_app, select.EPOLLIN)

        epoll_events_stop = select.epoll()
        epoll_events_stop.register(efd_stop_reloader, select.EPOLLIN)  # read
        epoll_events_stop.register(self.process_handles.efd_do_terminate_app, select.EPOLLIN)
        # process terminated unexpectedly (python exception on getting callable str)
        epoll_events_stop.register(self.process_handles.efd_process_terminated, select.EPOLLIN)

        while True:
            app_runner_thread = AppRunnerThread()
            app_runner_thread.set_process_handles(self.process_handles)

            logging.debug("AppRelaunchingThread:waiting for epoll_events_start")
            events = epoll_events_start.poll()
            for fileno, event in events:
                if fileno == efd_stop_reloader and event == select.EPOLLIN:
                    logger.debug("AppRelaunchingThread:epoll_events_start:efd_stop_reloader")
                    return
                elif fileno == self.process_handles.tfd_do_start_app and event == select.EPOLLIN:
                    logger.debug("AppRelaunchingThread:epoll_events_start:tfd_do_start_app")

                    # reset terminate flag, if still set (so we won't terminate immediately without reason)
                    try:
                        eventfd_res = eventfd_read(self.process_handles.efd_do_terminate_app)
                    except BlockingIOError as e:
                        # BlockingIOError: [Errno 11] Resource temporarily unavailable
                        if e.errno == 11:
                            pass
                        else:
                            raise

                    # reset timer
                    timerfd_read_res = timerfd_read(fileno)
                    # print("timerfd_read_res", timerfd_read_res)

                    # reset _app_starter flag
                    try:
                        eventfd_res2 = eventfd_read(self.process_handles.efd_process_started)
                        print("eventfd_res2", eventfd_res2)
                    except BlockingIOError as e:
                        # BlockingIOError: [Errno 11] Resource temporarily unavailable
                        if e.errno == 11:
                            pass
                        else:
                            raise

                    app_runner_thread.start()
                    #print("started thread")
                else:
                    raise Exception("should not happen: (fileno, event) (%s,%s)" % (fileno, event) )

            # FIXME: may be invoked multiple times
            # FIXME: spawned process may be set to None
            terminate_has_been_called = False
            def terminate_app():
                nonlocal terminate_has_been_called
                # print("terminate_app")
                if not terminate_has_been_called:
                    terminate_has_been_called = True
                    if app_runner_thread.is_alive():
                        self.process_handles.spawned_process.stop()
                        app_runner_thread.join()

            logging.debug("AppRelaunchingThread:waiting for epoll_events_stop")
            events = epoll_events_stop.poll()
            for fileno, event in events:
                if fileno == self.process_handles.efd_process_terminated and event == select.EPOLLIN:
                    # Either:
                    # 1) app terminated unexpectedly -> then other events won't be fired
                    # 2) normal shutdown signal -> then just pass
                    logging.debug("AppRelaunchingThread:epoll_events_stop:efd_process_terminated")
                    eventfd_read(fileno)
                    pass
                elif fileno == efd_stop_reloader and event == select.EPOLLIN:
                    logger.debug("AppRelaunchingThread:epoll_events_stop:efd_stop_reloader")
                    terminate_app()
                    return
                elif fileno == self.process_handles.efd_do_terminate_app and event == select.EPOLLIN:
                    logger.debug("AppRelaunchingThread:epoll_events_stop:efd_do_terminate_app")
                    eventfd_read(fileno)

                    terminate_app()
                    # and continue outer loop
                else:
                    raise Exception("should not happen: (fileno, event) (%s,%s)" % (fileno, event) )

            logging.debug("AppRelaunchingThread:loop over")

        logging.debug("AppRelaunchingThread:END")


class FileChangesMonitoringThread(threading.Thread):
    def set_process_handles(self, process_handles: ProcessHandles):
        self.process_handles = process_handles

    def run(self):
        inotify_fd = inotify_init1(IN_CLOEXEC | IN_NONBLOCK)

        watched_fds = {}

        def add_watch(full_path: bytes):
            c_path = create_string_buffer(full_path)

            watch_descriptor = inotify_add_watch(inotify_fd, c_path, IN_ALL_EVENTS & ~IN_ACCESS & ~IN_CLOSE & ~IN_OPEN)
            assert watch_descriptor != -1, "inotify_add_watch error"

            watched_fds[watch_descriptor] = full_path

        filesystemencoding = sys.getfilesystemencoding()

        # FIXME: use provided path
        # for root, dirs, files in os.walk('/home/ilja/Code/py_reload_inotify'):
        for root, dirs, files in os.walk(self.process_handles.launch_params.working_directory):
            add_watch(root.encode(filesystemencoding))

        def event_callback(full_path, event):
            # print("event_callback", full_path, event)
            if self.process_handles.launch_params.file_triggers_reload_fn(full_path):
                # start termination on first reload event
                logging.debug("event_callback:efd_do_terminate_app")
                eventfd_write(self.process_handles.efd_do_terminate_app, 1)

                set_do_start_timer(self.process_handles.tfd_do_start_app, after_ms=1)
                logging.debug("event_callback:END")
            else:
                pass

        ##

        epoll_events = select.epoll()
        epoll_events.register(inotify_fd, select.EPOLLIN)  # read
        epoll_events.register(efd_stop_reloader, select.EPOLLIN)  # read

        while True:
            events = epoll_events.poll()

            for fileno, event in events:
                if fileno == efd_stop_reloader and event == select.EPOLLIN:
                    logger.debug("FileChangesMonitoringThread:stop_reloader")
                    return
                elif fileno == inotify_fd and event == select.EPOLLIN:

                    start = default_timer()
                    for event in inotify_read(inotify_fd):
                        full_path = os.path.join(watched_fds[event.wd], event.name)

                        if event.mask & IN_CREATE and event.mask & IN_ISDIR:
                            add_watch(full_path)
                        elif event.mask & IN_IGNORED:
                            del watched_fds[event.wd]
                            continue  # to next event
                        elif event.mask & IN_UNMOUNT:
                            raise NotImplementedError("handling of IN_UNMOUNT")
                        elif event.mask & IN_Q_OVERFLOW:
                            raise NotImplementedError("handling of IN_Q_OVERFLOW")

                        event_callback(full_path, event)
                    diff = default_timer() - start
                    # print("Batch took: %.4f ms" % (diff * 1000))
                else:
                    raise Exception("should not happen")

# FIXME: naming
def main2_threaded(launch_params: LaunchParams):
    global efd_stop_reloader

    threads = []

    process_handles = ProcessHandles(launch_params)

    file_changes_monitoring_thread = FileChangesMonitoringThread()
    file_changes_monitoring_thread.set_process_handles(process_handles)
    threads.append(file_changes_monitoring_thread)
    file_changes_monitoring_thread.start()

    app_relaunching_thread = AppRelaunchingThread()
    app_relaunching_thread.set_process_handles(process_handles)
    threads.append(app_relaunching_thread)
    app_relaunching_thread.start()

    # start app
    set_do_start_timer(process_handles.tfd_do_start_app)

    try:
        select.select([], [], [])
    except KeyboardInterrupt as e:
        eventfd_write(efd_stop_reloader, 1)

    for thread in threads:
        logging.debug("joining: %s" % thread)
        thread.join()
        logging.debug("joined: %s" % thread)

    logging.debug("OVER")


def main(launch_params: LaunchParams):
    global efd_stop_reloader
    efd_stop_reloader = eventfd(0, flags=EFD_CLOEXEC | EFD_NONBLOCK)
    try:
        main2_threaded(launch_params)
    except KeyboardInterrupt as e:
        eventfd_write(efd_stop_reloader, 1)
