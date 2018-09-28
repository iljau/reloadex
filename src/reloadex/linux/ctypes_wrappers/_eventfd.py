import os
import struct

from ctypes import c_ulonglong, c_uint, c_int, get_errno

from reloadex.linux.ctypes_wrappers.common import libc, error_text

__all__ =  [
    "eventfd",
    "eventfd_write",
    "eventfd_read",
    "EFD_CLOEXEC",
    "EFD_NONBLOCK",
    "EFD_SEMAPHORE",
    "UINT64_MAX"
]

c_eventfd = libc.eventfd
c_eventfd.argtypes = [c_uint, c_int]

def res_c_eventfd(fd):
    if fd == -1:
        errno = get_errno()
        raise OSError(errno, error_text(errno))
    assert fd >= 0
    return fd

c_eventfd.restype = res_c_eventfd


UINT64_MAX = 2 ** 64 - 1

EFD_CLOEXEC = os.O_CLOEXEC
EFD_NONBLOCK = os.O_NONBLOCK
EFD_SEMAPHORE = 1 << 0


def _eventfd_value_check(value: int):
    if value < 0:
        raise Exception("Value should be >= 0")
    if value > UINT64_MAX-1:
        msg = "Value too large: %d > %d-1" % (value, UINT64_MAX)
        msg += "\nThe maximum value is the largest unsigned 64-bit value minus 1 (i.e., 0xfffffffffffffffe)."
        raise Exception(msg)


def eventfd(initial_value: int, flags: int):
    _eventfd_value_check(initial_value)

    # NOTE: initial value for c_eventfd in c_uint NOT c_ulonglong as used by write
    # so we do initial value setting in two steps
    fd = c_eventfd(0, flags)
    eventfd_write(fd, initial_value)
    return fd


def eventfd_write(fd, value: int) -> None:
    _eventfd_value_check(value)

    bytes_written = os.write(fd, c_ulonglong(value))
    if bytes_written != 8:
        raise Exception("bytes_written (%d) != 8", bytes_written)


def eventfd_read(fd) -> int:
    num = os.read(fd, 8)
    return struct.unpack('@Q', num)[0]
