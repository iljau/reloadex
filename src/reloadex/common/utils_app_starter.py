import importlib.util
import os
import sys


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