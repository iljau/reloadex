import ctypes
import ctypes.util
import errno
import os

libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)


def error_text(errnumber):
    return '%s: %s' % (errno.errorcode[errnumber], os.strerror(errnumber))