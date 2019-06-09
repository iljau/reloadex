import logging
import os
import select
import shlex
import signal
import threading

from reloadex.common.utils_reloader import LaunchParams
from reloadex.linux.ctypes_wrappers._eventfd import eventfd_write
from reloadex.linux.ctypes_wrappers._timerfd import timerfd_read
from reloadex.linux.reloader_linux import (
    FileChangesMonitoringThread, ProcessHandles, _SpawnedProcess
)
from reloadex.linux.shared import efd_stop_reloader

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())


class UwsgiAppRelaunchingThread(threading.Thread):
    def set_process_handles(self, process_handles: ProcessHandles):
        self.process_handles = process_handles

    def run(self):
        cmd_params = self.process_handles.launch_params.argparse_args.cmd_params
        _args = shlex.split(cmd_params[0])

        spawned_process = self.process_handles.spawned_process = _SpawnedProcess(
            _args,
            use_spawnp=True,
            termination_signal=signal.SIGQUIT
        )
        uwsgi_pid = spawned_process.start()

        ##
        ##

        epoll_events_start = select.epoll()
        epoll_events_start.register(efd_stop_reloader, select.EPOLLIN)  # read
        epoll_events_start.register(self.process_handles.tfd_do_start_app, select.EPOLLIN)

        while True:
            logger.debug("polling for startup")

            logger.debug("AppRelaunchingThread:waiting for epoll_events_start")
            events = epoll_events_start.poll()
            for fileno, event in events:
                logger.debug("some start event")

                if fileno == efd_stop_reloader and event == select.EPOLLIN:
                    logger.debug("AppRelaunchingThread:epoll_events_start:efd_stop_reloader")

                    logger.debug("stopping uwsgi process")

                    self.process_handles.spawned_process.stop()

                    return
                elif fileno == self.process_handles.tfd_do_start_app and event == select.EPOLLIN:
                    logger.debug("AppRelaunchingThread:epoll_events_start:tfd_do_start_app")

                    # reset timer (if set)
                    try:
                        timerfd_read_res = timerfd_read(fileno)
                    except BlockingIOError as e:
                        # BlockingIOError: [Errno 11] Resource temporarily unavailable
                        if e.errno == 11:
                            pass
                        else:
                            raise

                    logger.debug("restarting")

                    # brutally reload all the workers and the master process
                    # os.kill(uwsgi_pid, signal.SIGTERM)

                    # gracefully reload all the workers and the master process
                    os.kill(uwsgi_pid, signal.SIGHUP)

                    logger.debug("did restart")
                else:
                    raise Exception("should not happen: (fileno, event) (%s,%s)" % (fileno, event) )




# FIXME: naming
def main2_threaded(launch_params: LaunchParams):
    os.chdir(launch_params.working_directory)

    threads = []

    process_handles = ProcessHandles(launch_params)

    file_changes_monitoring_thread = FileChangesMonitoringThread()
    file_changes_monitoring_thread.set_process_handles(process_handles)
    threads.append(file_changes_monitoring_thread)
    file_changes_monitoring_thread.start()

    app_relaunching_thread = UwsgiAppRelaunchingThread()
    app_relaunching_thread.set_process_handles(process_handles)
    threads.append(app_relaunching_thread)
    app_relaunching_thread.start()

    try:
        select.select([], [], [])
    except KeyboardInterrupt as e:
        eventfd_write(efd_stop_reloader, 1)

    for thread in threads:
        logger.debug("joining: %s" % thread)
        thread.join()
        logger.debug("joined: %s" % thread)

    logger.debug("OVER")


def main(launch_params: LaunchParams):
    try:
        main2_threaded(launch_params)
    except KeyboardInterrupt as e:
        eventfd_write(efd_stop_reloader, 1)