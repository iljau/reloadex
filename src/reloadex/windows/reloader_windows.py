import threading
import os
import sys
import uuid

import pywintypes
import win32con
import win32console
import win32process
import win32api
import win32file
import win32pipe
import win32event

from pathspec import PathSpec

import logging

from reloadex.common.utils_reloader import LaunchParams

logger = logging.getLogger('reload_win32.reloader')
#logger.setLevel(logging.DEBUG)
consoleHandler = logging.StreamHandler()
logger.addHandler(consoleHandler)

# app_starter_windows_class_name = None

pipeName = r'\\.\pipe\%s' % uuid.uuid4()

callable_str = None
wd = None
cancel_termination_watching_event = win32event.CreateEvent(None, 0, 0, None)

hwndAppStarter = None


hpipe = win32pipe.CreateNamedPipe(
    pipeName,  # pipe name
    win32pipe.PIPE_ACCESS_DUPLEX |  # read/write access
    # win32pipe.PIPE_ACCESS_INBOUND|
    win32file.FILE_FLAG_OVERLAPPED,
    win32pipe.PIPE_TYPE_MESSAGE,  #|  # message-type pipe
    #win32pipe.PIPE_WAIT,  # blocking mode
    1,  # number of instances
    512,  # output buffer size
    512,  # input buffer size
    2000,  # client time-out
    None)  # no security attributes


def wait_for_client_init(hProcess):
    global hwndAppStarter
    logger.debug("connecting to pipe")

    overlapped = pywintypes.OVERLAPPED()
    pipe_connected_event = win32event.CreateEvent(None, 0, 0, None)
    overlapped.hEvent = pipe_connected_event


    res = win32pipe.ConnectNamedPipe(hpipe, overlapped)

    ###
    ###

    logger.debug("wait #1")
    ret = win32event.WaitForMultipleObjects(
        [hProcess, pipe_connected_event], False, win32event.INFINITE
    )
    event_i = ret - win32event.WAIT_OBJECT_0

    if event_i == 0:  # asked to cancel wait
        logger.debug("WAIT OVER: process terminated (PIPE!)")
        win32pipe.DisconnectNamedPipe(hpipe)
        return False
    elif event_i == 1:  # process terminated
        logger.debug("(PIPE CONNECTED!)")

        # depends on WINDOW_CLASS_NAME
        MESSAGE_LEN = 49

        logger.debug("start read")
        result, data = win32file.ReadFile(hpipe, MESSAGE_LEN)
        logger.debug("data: %s", data)
        # assert data == b"OK"
        logger.debug("end read")

        app_starter_windows_class_name = data.decode("utf-8")
        # print("window class name", app_starter_windows_class_name)
        hwndAppStarter = win32gui.FindWindow(app_starter_windows_class_name, None)

        win32pipe.DisconnectNamedPipe(hpipe)
        return True
    else:
        raise Exception("unexpected ret or event_id", ret, event_i)


class ProcessHandler(object):
    def __init__(self):
        self.hProcess = None
        self.hThread = None
        self.pid = None

        self.is_starting = False
        self.accept_new = True
        self.ctrl_c_sent = False

    def register_ctrl_handler(self):
        # register before creating subprocess
        win32api.SetConsoleCtrlHandler(self.ctrl_handler, True)

    def ctrl_handler(self, event):
        logger.debug("main_process:ctrl_handler %s", event)
        if event == win32console.CTRL_C_EVENT:
            if self.pid is not None:
                win32api.GenerateConsoleCtrlEvent(win32console.CTRL_BREAK_EVENT, self.pid)
            return False
        elif event == win32console.CTRL_BREAK_EVENT:
            # assume win32console.CTRL_BREAK_EVENT
            if self.is_process_active() and self.pid is not None:
                # invoke subprocess handler
                return True
            else:
                # allow exit
                return False
        else:
            return False

    def is_process_active(self):
        if self.hProcess is None:
            return False

        try:
            ret = win32process.GetExitCodeProcess(self.hProcess)
            return ret == win32con.STILL_ACTIVE
        except Exception as e:
            # TODO: handle .error: (6, 'GetExitCodeProcess', 'The handle is invalid.')
            #print repr(e)
            return False

    def termination_watcher(self):
        logger.debug("wait #1")
        ret = win32event.WaitForMultipleObjects(
            [cancel_termination_watching_event, self.hProcess], False, win32event.INFINITE
        )
        event_i = ret - win32event.WAIT_OBJECT_0

        if event_i == 0: # asked to cancel wait
            logger.debug("WAIT OVER: asked to cancel wait")
            pass
        elif event_i == 1:  # process terminated
            logger.debug("WAIT OVER: process terminated")
            pass
        else:
            raise Exception("unexpected ret or event_id", ret, event_i)

    def start_process(self):
        assert self.hProcess is None
        assert self.hThread is None
        assert self.pid is None
        assert self.is_starting == False

        self.is_starting = True

        # use main process stdout and stderr
        startup_info = win32process.STARTUPINFO()
        startup_info.hStdOutput = win32file._get_osfhandle(sys.stdout.fileno())
        startup_info.hStdError = win32file._get_osfhandle(sys.stderr.fileno())
        startup_info.hStdInput = win32file._get_osfhandle(sys.stdin.fileno())
        startup_info.dwFlags = win32process.STARTF_USESTDHANDLES

        # "some_app:run"
        target_fn_str = callable_str
        app_starter = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_app_starter.py")
        cmdline = '''"%s" -u "%s" "%s" "%s" ''' % (sys.executable, app_starter, target_fn_str, pipeName)

        self.hProcess, self.hThread, self.pid, dwTid = t = win32process.CreateProcess(
            None, cmdline, None, None, 1, 0, None, wd, startup_info)

        t_termination_watcher = threading.Thread(target=self.termination_watcher)
        t_termination_watcher.start()

        logger.debug("waiting for client init")

        client_inited = wait_for_client_init(self.hProcess)
        self.is_starting = False
        if client_inited:
            logger.debug("client inited")
        else:
            logger.debug("python process DID NOT INIT!")
            self.post_terminate()

    def post_terminate(self):
        assert self.hProcess is not None
        assert self.hThread is not None

        win32event.WaitForSingleObject(self.hProcess, win32event.INFINITE)
        assert self.is_process_active() == False

        win32api.CloseHandle(self.hProcess)
        self.hProcess = None

        win32api.CloseHandle(self.hThread)
        self.hThread = None

        self.pid = None

    def terminate_if_needed(self):
        if self.hProcess is not None or self.hThread is not None:
            self.do_terminate()

    def do_terminate(self):
        assert self.hProcess is not None
        assert self.hThread is not None

        from timeit import default_timer
        start = default_timer()

        graceful = True
        if graceful:
            win32api.SendMessage(hwndAppStarter, win32con.WM_DESTROY, 0, 0)
        else:
            win32api.TerminateProcess(self.hProcess, 15)

        self.post_terminate()

        # If the HandlerRoutine parameter is NULL, a TRUE value causes
        #  the calling process to ignore CTRL+C input, and a FALSE value
        #  restores normal processing of CTRL+C input. This attribute of ignoring or processing CTRL+C is inherited by child processes.
        #
        # TODO: ??? not sure why, but disabling this makes things work in PyCharm
        win32api.SetConsoleCtrlHandler(None, False)

        diff = default_timer() - start
        logger.debug("Termination took: %.4f" % diff)

###
###


process_handler = None # type: ProcessHandler
terminate_event = win32event.CreateEvent(None, 0, 0, None)
restart_event = win32event.CreateWaitableTimer(None, 0, None)
RESTART_EVENT_DT = -1000 * 100 * 5 # 0.05s

spec = None

reload_lock = threading.Lock()

DEFAULT_RELOADIGNORE = """
# Ignore everything ..
*
*/

# .. except *.py files
!*.py
"""


def reload_ignore_config():
    global spec
    with reload_lock:
        try:
            with open('.reloadignore', 'r') as fh:
                spec = PathSpec.from_lines('gitwildmatch', fh)
        except IOError as e:
            if e.errno == 2:
                logger.info("'.reloadignore' not found. Using default spec.")
                spec = PathSpec.from_lines('gitwildmatch', DEFAULT_RELOADIGNORE.splitlines())
            else:
                raise


def file_triggers_reload(filename):
    global spec
    return not spec.match_file(filename)


# http://timgolden.me.uk/python/win32_how_do_i/watch_directory_for_changes.html
def my_win32_watcher():
    CREATED = 1
    DELETED = 2
    UPDATED = 3
    RENAMED_FROM = 4
    RENAMED_TO = 5

    ACTIONS = {
        1: "Created",
        2: "Deleted",
        3: "Updated",
        4: "Renamed from something",
        5: "Renamed to something"
    }
    # Thanks to Claudio Grondi for the correct set of numbers
    FILE_LIST_DIRECTORY = 0x0001

    path_to_watch = "."
    hDir = win32file.CreateFile(
        path_to_watch,
        FILE_LIST_DIRECTORY,
        win32con.FILE_SHARE_READ | win32con.FILE_SHARE_WRITE | win32con.FILE_SHARE_DELETE,
        None,
        win32con.OPEN_EXISTING,
        win32con.FILE_FLAG_BACKUP_SEMANTICS,
        None
    )
    while 1:
        #
        # ReadDirectoryChangesW takes a previously-created
        # handle to a directory, a buffer size for results,
        # a flag to indicate whether to watch subtrees and
        # a filter of what changes to notify.
        #
        # NB Tim Juchcinski reports that he needed to up
        # the buffer size to be sure of picking up all
        # events when a large number of files were
        # deleted at once.
        #
        results = win32file.ReadDirectoryChangesW(
            hDir,
            1024,
            True,
            win32con.FILE_NOTIFY_CHANGE_FILE_NAME |
            win32con.FILE_NOTIFY_CHANGE_DIR_NAME |
            win32con.FILE_NOTIFY_CHANGE_ATTRIBUTES |
            win32con.FILE_NOTIFY_CHANGE_SIZE |
            win32con.FILE_NOTIFY_CHANGE_LAST_WRITE |
            win32con.FILE_NOTIFY_CHANGE_SECURITY,
            None,
            None
        )

        do_reload = False
        for action, file_path in results:
            if file_path == ".reloadignore":
                logger.debug("reloading ignore config")
                reload_ignore_config()

            if file_triggers_reload(file_path):
                #l = file_path, file_triggers_reload(file_path)
                do_reload = True
                break

        if do_reload:
            # terminate on first file change
            win32event.SetEvent(terminate_event)

            # 50 ms rollup window for starting reloading
            win32event.CancelWaitableTimer(restart_event)
            win32event.SetWaitableTimer(restart_event, RESTART_EVENT_DT, 0, None, None, 0)


def send_initial_restarter_signals():
    win32event.SetEvent(terminate_event)
    win32event.SetWaitableTimer(restart_event, 0, 0, None, None, 0)


def restarter():
    global process_handler
    while True:
        logger.debug("waiting for terminate_event")
        win32event.WaitForSingleObject(terminate_event, win32event.INFINITE)

        logger.debug("restarting")
        process_handler.terminate_if_needed()

        logger.debug("waiting for restart_event")
        win32event.WaitForSingleObject(restart_event, win32event.INFINITE)

        logger.debug("doing start_process")
        process_handler.start_process()
        logger.debug("process started")

        win32event.ResetEvent(terminate_event)
        logger.debug("restarter_loop_over")


def my_exit(event):
    logger.debug("my_exit: %s", event)
    if event == win32console.CTRL_BREAK_EVENT:
        return True
    else:
        os._exit(11)


###
###
###

import uuid
import atexit

import win32api
import win32con
import win32gui


def reloader_atexit():
    # invoked last (after pywin32 is over)
    logger.debug("reloader_atexit")


class Config:
    WINDOW_CLASS_NAME = "reloader_%s" % uuid.uuid4()


class ReloaderMain:
    def __init__(self):
        global process_handler

        self.window_class_name = Config.WINDOW_CLASS_NAME

        # Register the Window class.
        window_class = win32gui.WNDCLASS()
        hInst = window_class.hInstance = win32gui.GetModuleHandle(None)
        window_class.lpszClassName = self.window_class_name
        window_class.lpfnWndProc = self.pyWndProcedure  # could also specify a wndproc.
        classAtom = win32gui.RegisterClass(window_class)

        # Create the Window.
        style = win32con.WS_OVERLAPPED | win32con.WS_SYSMENU
        self.hWnd = win32gui.CreateWindow(classAtom,
                                          self.window_class_name,
                                          style,
                                          0,
                                          0,
                                          win32con.CW_USEDEFAULT,
                                          win32con.CW_USEDEFAULT,
                                          0,
                                          0,
                                          hInst,
                                          None)

        # init activate restarter loop
        send_initial_restarter_signals()

        # loop
        win32gui.UpdateWindow(self.hWnd)
        postQuitExitCode = win32gui.PumpMessages()

        # TODO: before quit need to do following
        # and this has to done immediately after PumpMessages is over
        # -> when we close console, then we may time-out before finishing timeout
        # print("postQuitExitCode", postQuitExitCode)

        win32gui.DestroyWindow(self.hWnd)
        win32gui.UnregisterClass(window_class.lpszClassName, hInst)
        # print("after after")

    def pyWndProcedure(self, hWnd, uMsg, wParam, lParam):
        def default():
            return win32gui.DefWindowProc(hWnd, uMsg, wParam, lParam)

        # FIXME: handle when console window is closed (by x)

        # create stuff doesn't appear to be used
        if False:
            pass
        elif uMsg == win32con.WM_NCCREATE:  # 1st according to docs, but not invoked
            # print("WM_NCCREATE")
            return 0
        elif uMsg == win32con.WM_CREATE:  # 2nd according to docs, but not actually invoked
            # print("WM_CREATE")
            return 0
        elif uMsg == win32con.WM_NCDESTROY:  # 130 -> last message
            # print("WM_NCDESTROY")
            win32api.PostQuitMessage(0)
            return default()
        elif uMsg == win32con.WM_DESTROY:  # 2 -> second to last
            # print("WM_DESTROY")
            win32api.PostQuitMessage(0)
            return default()
        else:
            return default()


mainThreadId = win32api.GetCurrentThreadId()


# https://docs.microsoft.com/en-us/windows/console/handlerroutine
def _console_exit_handler(dwCtrlType):
    # print("_console_exit_handler")

    # if we get threadId from here, it's different, than main
    # print("t3", mainThreadId)

    # FROM: https://docs.microsoft.com/en-gb/windows/desktop/winmsg/wm-quit
    # "Do not post the WM_QUIT message using the PostMessage function; use PostQuitMessage."
    # BUT: WM_QUIT did work, PostQuitMessage didn't, win32con.WM_DESTROY didn't either

    wParam = 1  # postQuitExitCode gets this
    lParam = 2  # not sure if used
    win32api.PostThreadMessage(mainThreadId, win32con.WM_QUIT, wParam, lParam)
    # win32gui.PostThreadMessage(mainThreadId, win32con.WM_NULL, 0, 0)

    return True

    # 1) this handles ctrl+c, allows atexit handler to run
    # 2) silences: ConsoleCtrlHandler function failed -> but tray icon doesn't disappear
    # sys.stderr = open(os.devnull, 'w')
    # sys.exit(0)


###
###
###


def main(launch_params: LaunchParams):
    global process_handler
    global callable_str
    global wd
    global reloader_main

    wd = launch_params.working_directory
    callable_str = launch_params.target_fn_str

    reload_ignore_config()

    process_handler = ProcessHandler()

    win32api.SetConsoleCtrlHandler(my_exit, True)
    # TODO: not sure why, but disabling this makes things work in PyCharm
    # process_handler.register_ctrl_handler()

    t2 = threading.Thread(target=restarter)
    t2.setDaemon(True)
    t2.start()

    t3 = threading.Thread(target=my_win32_watcher)
    t3.setDaemon(True)
    t3.start()

    atexit.register(reloader_atexit)
    win32api.SetConsoleCtrlHandler(_console_exit_handler, True)

    # FIXME: separate init and run
    # FIXME: list identifiers
    ReloaderMain()


if __name__ == "__main__":
    main()


