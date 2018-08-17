import os
import sys
import uuid
import atexit
import threading
import importlib
import importlib.util

import win32api
import win32file
import win32console
import win32con
import win32gui


# FIXME: logging line format
import logging
logger = logging.getLogger('reload_win32._app_starter')
logger.setLevel(logging.INFO)
consoleHandler = logging.StreamHandler()
logger.addHandler(consoleHandler)


mainThreadId = None


def set_inited(pipeName, message):
    fileHandle = win32file.CreateFile(pipeName,
                                      win32file.GENERIC_WRITE,
                                      0, None,
                                      win32file.OPEN_EXISTING,
                                      0, None)

    logger.debug("starting write")
    wres = win32file.WriteFile(fileHandle, message)
    logger.debug(wres)
    logger.debug("write over")
    win32api.CloseHandle(fileHandle)


def get_main_function(module, fn_name):
    attr = module
    # allow 'some.attribute.nesting'
    for attr_name in fn_name.split("."):
        attr = getattr(attr, attr_name)
    fn = attr
    return fn


def get_callable_by_ref(module_name, function_name, folder):
    if folder not in sys.path:
        sys.path.append(os.getcwd())

    _module = importlib.import_module(module_name)

    return get_main_function(_module, function_name)


def get_callable_by_file(filename, function_name, folder):
    only_filename = os.path.basename(filename)
    assumed_module_name = os.path.splitext(only_filename)[0]

    spec = importlib.util.spec_from_file_location(assumed_module_name, filename)
    _module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(_module)

    return get_main_function(_module, function_name)


def get_callable(target_str, folder):
    if ":" not in target_str:
        _target_str = target_str
        _function_str = "main"
    else:
        _target_str, _function_str = target_str.split(":")

    if os.path.isfile(_target_str):
        return get_callable_by_file(filename=_target_str, function_name=_function_str, folder=folder)
    else:
        return get_callable_by_ref(module_name=_target_str, function_name=_function_str, folder=folder)

####
####
####


def _app_starter_atexit():
    logger.debug("_app_starter_atexit")


class Config:
    # 49 bytes
    WINDOW_CLASS_NAME = "_app_starter_%s" % uuid.uuid4()


class AppStarterMain:
    def __init__(self, server_fn, pipeName):
        global process_handler

        self.window_class_name = Config.WINDOW_CLASS_NAME
        # print("len()", len(self.window_class_name), self.window_class_name)

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

        #
        # BEGIN actual setup
        #

        t = threading.Thread(target=server_fn)
        t.setDaemon(True)
        t.start()

        set_inited(pipeName, bytes(self.window_class_name.encode('utf-8')))

        #
        # END actual setup
        #

        # loop
        win32gui.UpdateWindow(self.hWnd)
        postQuitExitCode = win32gui.PumpMessages()

        # TODO: before quit need to do following
        # and this has to done immediately after PumpMessages is over
        # -> when we close console, then we may time-out before finishing timeout
        logger.debug("_app_starter: postQuitExitCode", postQuitExitCode)

        win32gui.DestroyWindow(self.hWnd)
        win32gui.UnregisterClass(window_class.lpszClassName, hInst)
        logger.debug("_app_starter: after after")

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
            # print("uMsg", uMsg)
            return default()


# https://docs.microsoft.com/en-us/windows/console/handlerroutine
def _console_exit_handler(dwCtrlType):
    # print("_app_starter: _console_exit_handler")

    # FROM: https://docs.microsoft.com/en-gb/windows/desktop/winmsg/wm-quit
    # "Do not post the WM_QUIT message using the PostMessage function; use PostQuitMessage."
    # BUT: WM_QUIT did work, PostQuitMessage didn't, win32con.WM_DESTROY didn't either

    wParam = 1  # postQuitExitCode gets this
    lParam = 2  # not sure if used
    win32api.PostThreadMessage(mainThreadId, win32con.WM_QUIT, wParam, lParam)

    return True


def main():
    global mainThreadId

    fn = get_callable(sys.argv[1], os.getcwd())
    pipeName = sys.argv[2]

    # FIXME: move to more obvious place
    mainThreadId = win32api.GetCurrentThreadId()

    atexit.register(_app_starter_atexit)
    win32api.SetConsoleCtrlHandler(_console_exit_handler, True)

    # FIXME: separate init and run
    AppStarterMain(server_fn=fn, pipeName=pipeName)


if __name__ == "__main__":
    main()



