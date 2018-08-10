import os
import sys
import importlib

import win32api
import win32file
import win32console

# FIXME: logging line format
import logging
logger = logging.getLogger('reload_win32._app_started')
logger.setLevel(logging.INFO)
consoleHandler = logging.StreamHandler()
logger.addHandler(consoleHandler)

def terminate_app(event):
    # avoid: ConsoleCtrlHandler function failedException KeyError: KeyError(13548,) in <module 'threading' from '\lib\threading.pyc'> ignored
    sys.stderr = open(os.devnull, 'w')
    #logging.info("app_starter:terminate_app", event)

    # when terminal window is closed in windows
    CTRL_CLOSE_EVENT = 2

    if event == win32console.CTRL_BREAK_EVENT:
        # causes: "ConsoleCtrlHandler function failed"
        # causes: threading exception logging, but atexit handlers are run
        sys.exit(-1)
    elif event == CTRL_CLOSE_EVENT:
        # console window closed
        sys.exit(-1)
        #return False
    else:
        return True


def set_inited():
    # FIXME: don't hard-code pipe name
    pipeName = r'\\.\pipe\mypipe123'
    fileHandle = win32file.CreateFile(pipeName,
                                      win32file.GENERIC_WRITE,
                                      0, None,
                                      win32file.OPEN_EXISTING,
                                      0, None)

    logger.debug("starting write")
    wres = win32file.WriteFile(fileHandle, b"OK")
    logger.debug(wres)
    logger.debug("write over")
    win32api.CloseHandle(fileHandle)


def get_callable(target_fn_str, folder):
    if folder not in sys.path:
        sys.path.append(os.getcwd())

    _module_str, _function_str = target_fn_str.split(":")
    _module = importlib.import_module(_module_str)

    attr = _module
    for attr_name in _function_str.split("."):
        attr = getattr(attr, attr_name)
    fn = attr
    return fn


def main():
    fn = get_callable(sys.argv[1], os.getcwd())

    set_inited()

    win32api.SetConsoleCtrlHandler(terminate_app, True)

    fn()


if __name__ == "__main__":
    main()



