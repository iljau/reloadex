import os
import sys
import importlib
import importlib.util

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
    print("terminate_app", event)

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


def set_inited(pipeName):
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


def main():
    fn = get_callable(sys.argv[1], os.getcwd())
    pipeName = sys.argv[2]

    set_inited(pipeName)

    win32api.SetConsoleCtrlHandler(terminate_app, True)

    fn()


if __name__ == "__main__":
    main()



