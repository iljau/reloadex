import signal
from _ctypes import get_errno

from ctypes import c_int, c_ulong

# int prctl(int option, unsigned long arg2, unsigned long arg3,
#                  unsigned long arg4, unsigned long arg5);
from reloadex.linux.ctypes_wrappers.common import error_text, libc

prctl = libc.prctl
prctl.argtypes = [c_int, c_ulong, c_ulong, c_ulong, c_ulong]
def res_prctl(r):
    if r == -1:
        errno = get_errno()
        raise OSError(errno, error_text(errno))
    assert r >= 0
    return r
prctl.restype = res_prctl


PR_SET_PDEATHSIG = 1
SIGTERM = signal.SIGTERM  # 15