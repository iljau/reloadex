# https://github.com/yrro/pilight/blob/0d0b40e68d03fbbf01e496a6a8e12cac865a4810/ctimerfd.py
import ctypes
import ctypes.util
import os
import struct
from _ctypes import Structure, POINTER, get_errno
from ctypes import cdll, c_int, c_long, CDLL

from reloadex.linux.ctypes_wrappers.common import error_text, libc

__all__ = [
    "CLOCK_MONOTONIC",
    "TFD_CLOEXEC",
    "TFD_NONBLOCK",
    "timerfd_create",
    "timerfd_settime",
    "itimerspec",
    "timespec",
    "timerfd_read"
]

#linux/time.h
#49:#define CLOCK_MONOTONIC			1

CLOCK_MONOTONIC = 1

# #    TFD_CLOEXEC = 02000000,
# #define TFD_CLOEXEC TFD_CLOEXEC
# #    TFD_NONBLOCK = 00004000
# #define TFD_NONBLOCK TFD_NONBLOCK
TFD_CLOEXEC = os.O_CLOEXEC
TFD_NONBLOCK = os.O_NONBLOCK

# int timerfd_create(int clockid, int flags);
timerfd_create = libc.timerfd_create
timerfd_create.argtypes = [c_int, c_int]
def res_timerfd_create(fd):
    if fd == -1:
        errno = get_errno()
        raise OSError(errno, error_text(errno))
    assert fd >= 0
    return fd

timerfd_create.restype = res_timerfd_create


# #define __SLONGWORD_TYPE	long int
# # define __SYSCALL_SLONG_TYPE	__SLONGWORD_TYPE
# #define __TIME_T_TYPE		__SYSCALL_SLONG_TYPE
# __STD_TYPE __TIME_T_TYPE __time_t;	/* Seconds since the Epoch.  */

# /* Signed long type used in system calls.  */
# __STD_TYPE __SYSCALL_SLONG_TYPE __syscall_slong_t;

# struct timespec
# {
#   __time_t tv_sec;		/* Seconds.  */
#   __syscall_slong_t tv_nsec;	/* Nanoseconds.  */
# };

class timespec(Structure):
    _fields_ = [("tv_sec", c_long), ("tv_nsec", c_long)]

# struct itimerspec
#   {
#     struct timespec it_interval;
#     struct timespec it_value;
#   };
class itimerspec(Structure):
    _fields_ = [("it_interval", timespec), ("it_value", timespec)]


# int timerfd_settime(int fd, int flags,
#                            const struct itimerspec *new_value,
#                            struct itimerspec *old_value);
timerfd_settime = libc.timerfd_settime
timerfd_settime.argtypes = [c_int, c_int, POINTER(itimerspec), POINTER(itimerspec)]
def res_timerfd_settime(r):
    if r == -1:
        errno = get_errno()
        raise OSError(errno, error_text(errno))
    assert r >= 0
    return r
timerfd_settime.restype = res_timerfd_settime


def timerfd_read(fd) -> int:
    # read(2) returns an unsigned 8-byte integer (uint64_t) containing the
    # number of expirations that have occurred.
    # (The returned value
    # is in host byte order—that is, the native byte order for inte‐
    # gers on the host machine.)
    read_buffer = os.read(fd, 8)
    return struct.unpack('@Q', read_buffer)[0]