import signal
import threading
import os
import sys
import uuid
import atexit
from logging import BASIC_FORMAT
from time import sleep
from timeit import default_timer

import pywintypes
import win32api
import win32con
import win32console
import win32gui
import win32process
import win32file
import win32pipe
import win32event


from pathspec import PathSpec

import logging

from reloadex.common.utils_app_starter import is_target_str_file
from reloadex.common.utils_reloader import LaunchParams

logger = logging.getLogger('reload_win32.reloader')
# logger.setLevel(logging.DEBUG)
consoleHandler = logging.StreamHandler()
formatter = logging.Formatter(logging.BASIC_FORMAT)
consoleHandler.setFormatter(formatter)
logger.addHandler(consoleHandler)

# app_starter_windows_class_name = None

pipeName = r'\\.\pipe\%s' % uuid.uuid4()

###

# https://github.com/mozilla/build-tools/blob/c212285a4936566b6761b83bb6b6136c88b4383c/buildfarm/utils/win32_util.py
hKernel = win32api.GetModuleHandle("Kernel32")
exitThread = win32api.GetProcAddress(hKernel, "ExitThread")

###

# callable_str = None
workingDirectory = None
cancel_termination_watching_event = win32event.CreateEvent(None, 0, 0, None)
createProcess_cmdline = None

hwndAppStarter = None


class ProcessHandler(object):
    def __init__(self):
        self.hProcess = None
        self.hThread = None
        self.pid = None
        self.dwThreadId = None

        self.is_starting = False

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

    def start_process(self):
        global should_ignore_ctrl_c
        global createProcess_cmdline

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

        self.hProcess, self.hThread, self.pid, self.dwThreadId = t = win32process.CreateProcess(
            None, createProcess_cmdline, None, None, 1, 0, None, workingDirectory, startup_info)

        try:
            hRemoteThread, remoteThreadId = win32process.CreateRemoteThread(self.hProcess, None, 0, exitThread, -1, 0)
            logger.info("hRemote: %s %s" % (hRemoteThread, remoteThreadId))
        except pywintypes.error as e:
            print(e)
            if e.winerror == 5:
                # (5, 'CreateRemoteThread', 'Access is denied.')
                # if process exists before we make to create remote thread
                self.is_starting = False
                return
            else:
                raise

        logger.debug("### wait #123")
        ret = win32event.WaitForMultipleObjects(
            [hRemoteThread, self.hProcess], False, win32event.INFINITE
        )
        event_i = ret - win32event.WAIT_OBJECT_0
        if event_i == 0:
            logger.debug("### hRemoteThread was executed")
            pass
        elif event_i == 1:
            # process terminated (unexpectedly)
            logger.debug("### WAIT OVER: process terminated (unexpectedly)")
            self.post_terminate()
        else:
            raise Exception("unexpected ret or event_id", ret, event_i)

        self.is_starting = False

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
        self.dwThreadId = None

    def terminate_if_needed(self):
        if self.hProcess is not None or self.hThread is not None:
            self.do_terminate()

    def do_terminate(self):
        assert self.hProcess is not None
        assert self.hThread is not None

        start = default_timer()

        logging.debug("ATTEMPT at termination")
        graceful = True
        if graceful:
            logging.debug("### send Ctrl+C")
            # avoid terminating our process
            win32api.SetConsoleCtrlHandler(None, True)
            win32api.GenerateConsoleCtrlEvent(win32console.CTRL_C_EVENT, self.pid)
        else:
            win32api.TerminateProcess(self.hProcess, 15)
        self.post_terminate()
        logging.debug("POST terminate DONE")

        # If the HandlerRoutine parameter is NULL,  a
        # TRUE value causes the calling process to ignore CTRL+C input, and a
        # FALSE value restores normal processing of CTRL+C input. This attribute of ignoring or processing CTRL+C is inherited by child processes.
        #
        # HAS TO BE called AFTER process has been terminated
        win32api.SetConsoleCtrlHandler(None, False)

        diff = default_timer() - start
        logger.debug("Termination took: %.4f" % diff)

        logging.debug("TERMINATE OVER")

###
###


process_handler = None # type: ProcessHandler
terminate_event = win32event.CreateEvent(None, 0, 0, None)
restart_event = win32event.CreateWaitableTimer(None, 0, None)
# RESTART_EVENT_DT = -1000 * 100 * 5 # 0.05s
RESTART_EVENT_DT = 1

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
        # FIXME: restore waiting
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


# doesn't appear to be invoked
def my_exit(event):
    logger.debug("my_exit: %s", event)
    print("my_exit: %s", event)
    if event == win32console.CTRL_BREAK_EVENT:
        return True
    else:
        os._exit(11)


###
###
###



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
    logging.debug("_console_exit_handler %s" % dwCtrlType)

    # if we get threadId from here, it's different, than main
    # print("t3", mainThreadId)

    # FROM: https://docs.microsoft.com/en-gb/windows/desktop/winmsg/wm-quit
    # "Do not post the WM_QUIT message using the PostMessage function; use PostQuitMessage."
    # BUT: WM_QUIT did work, PostQuitMessage didn't, win32con.WM_DESTROY didn't either

    wParam = 1  # postQuitExitCode gets this
    lParam = 2  # not sure if used
    logging.debug("posting WM_QUIT")
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
    global workingDirectory
    global reloader_main
    global createProcess_cmdline

    workingDirectory = launch_params.working_directory

    argparse_args = launch_params.argparse_args

    # FIXME: quote arguments correctly
    #  https://blogs.msdn.microsoft.com/twistylittlepassagesallalike/2011/04/23/everyone-quotes-command-line-arguments-the-wrong-way/
    if argparse_args.cmd == False:
        # FIXME: "app.py" should be launched directly using python
        target_str = argparse_args.cmd_params[0]
        # -u: Force the stdout and stderr streams to be unbuffered. See also PYTHONUNBUFFERED.
        # -B: don't try to write .pyc files on the import of source modules. See also PYTHONDONTWRITEBYTECODE.
        if is_target_str_file(target_str):
            logging.debug("RUN #1")
            py_script_path = target_str
            createProcess_cmdline = '''"%s" -u -B "%s" ''' % (sys.executable, py_script_path)
        else:
            logging.debug("RUN #2")
            # our start
            # "some_app:run"
            target_fn_str = target_str
            app_starter = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_app_starter.py")
            createProcess_cmdline = '''"%s" -u -B "%s" "%s" ''' % (sys.executable, app_starter, target_fn_str)
    else:
        cmd_params = argparse_args.cmd_params
        if len(cmd_params) == 1:
            logging.debug("RUN #3")
            # 'gunicorn app:app' -> as single string
            createProcess_cmdline = cmd_params[0]
        else:
            logging.debug("RUN #4")
            createProcess_cmdline = " ".join(cmd_params)

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

