# https://github.com/osandov/molino/blob/75124a6ceb0a55ace15bd7d6539f7c1818ab0d8c/molino/signalfd.py
# https://github.com/bretttegart/treadmill-elbplugin/blob/99b87bf37d7df784e9234eda6b367237b4b72246/lib/python/treadmill/syscall/signalfd.py
import os
from ctypes import *

from reloadex.linux.ctypes_wrappers.common import libc, error_text

__all__ = [
    "sigset_t",

    "signalfd",
    "sigemptyset",
    "sigfillset",
    "sigaddset",
    "sigdelset",
    "sigprocmask",

    "SFD_CLOEXEC",
    "SFD_NONBLOCK",

    "signalfd_read"
]

# typedef __sigset_t sigset_t;
# #define _SIGSET_NWORDS (1024 / (8 * sizeof (unsigned long int)))
# typedef struct
# {
#   unsigned long int __val[_SIGSET_NWORDS];
# } __sigset_t;

_SIGSET_NWORDS = int(1024 / (8 * sizeof(c_ulong)))
# # should be 16
# print(_SIGSET_NWORDS)
assert _SIGSET_NWORDS == 16

class sigset_t(Structure):
    _fields_ = [
        ("__val", c_ulong * _SIGSET_NWORDS) # pid_t
    ]

# should be 128
assert sizeof(sigset_t) == 128

#     SFD_CLOEXEC = 02000000,
# #define SFD_CLOEXEC SFD_CLOEXEC
#     SFD_NONBLOCK = 00004000
# #define SFD_NONBLOCK SFD_NONBLOCK

SFD_CLOEXEC = os.O_CLOEXEC
SFD_NONBLOCK = os.O_NONBLOCK

#  int signalfd(int fd, const sigset_t *mask, int flags);
signalfd = libc.signalfd
signalfd.argtypes = [c_int, POINTER(sigset_t), c_int]
def res_signalfd(fd):
    if fd == -1:
        errno = get_errno()
        raise OSError(errno, error_text(errno))
    assert fd >= 0
    return fd
signalfd.restype = res_signalfd

###
###

def res_sig_fns(errno):
    if errno != 0:
        raise OSError(errno, error_text(errno))
    return errno

# int sigemptyset(sigset_t *set);
sigemptyset = libc.sigemptyset
sigemptyset.argtypes = [POINTER(sigset_t)]
sigemptyset.restype = res_sig_fns

# /* Set all signals in SET.  */
# extern int sigfillset (sigset_t *__set) __THROW __nonnull ((1));
sigfillset = libc.sigfillset
sigfillset.argtypes = [POINTER(sigset_t)]
sigfillset.restype = res_sig_fns

# int sigaddset(sigset_t *set, int signum);
sigaddset = libc.sigaddset
sigaddset.argtypes = [POINTER(sigset_t), c_int]
sigaddset.restype = res_sig_fns

# int sigdelset(sigset_t *set, int signo);
sigdelset = libc.sigdelset
sigdelset.argtypes = [POINTER(sigset_t), c_int]
sigdelset.restype = res_sig_fns

# int sigprocmask(int how, const sigset_t *set, sigset_t *oldset);
sigprocmask = libc.sigprocmask
sigprocmask.argtypes = [c_int, POINTER(sigset_t), POINTER(sigset_t)]
sigprocmask.restype = res_sig_fns


# struct signalfd_siginfo {
#    uint32_t ssi_signo;    /* Signal number */
#    int32_t  ssi_errno;    /* Error number (unused) */
#    int32_t  ssi_code;     /* Signal code */
#    uint32_t ssi_pid;      /* PID of sender */
#    uint32_t ssi_uid;      /* Real UID of sender */
#    int32_t  ssi_fd;       /* File descriptor (SIGIO) */
#    uint32_t ssi_tid;      /* Kernel timer ID (POSIX timers)
#    uint32_t ssi_band;     /* Band event (SIGIO) */
#    uint32_t ssi_overrun;  /* POSIX timer overrun count */
#    uint32_t ssi_trapno;   /* Trap number that caused signal */
#    int32_t  ssi_status;   /* Exit status or signal (SIGCHLD) */
#    int32_t  ssi_int;      /* Integer sent by sigqueue(3) */
#    uint64_t ssi_ptr;      /* Pointer sent by sigqueue(3) */
#    uint64_t ssi_utime;    /* User CPU time consumed (SIGCHLD) */
#    uint64_t ssi_stime;    /* System CPU time consumed
#                              (SIGCHLD) */
#    uint64_t ssi_addr;     /* Address that generated signal
#                              (for hardware-generated signals) */
#    uint16_t ssi_addr_lsb; /* Least significant bit of address
#                              (SIGBUS; since Linux 2.6.37)
#    uint8_t  pad[X];       /* Pad size to 128 bytes (allow for
#                              additional fields in the future) */
# };

class signalfd_siginfo(Structure):
    _FIELDS = [
        ('ssi_signo', c_uint32),    #: Signal number
        ('ssi_errno', c_int32),     #: Error number (unused)
        ('ssi_code', c_int32),      #: Signal code
        ('ssi_pid', c_uint32),      #: PID of sender
        ('ssi_uid', c_uint32),      #: Real UID of sender
        ('ssi_fd', c_int32),        #: File descriptor (SIGIO)
        ('ssi_tid', c_uint32),      #: Kernel timer ID (POSIX timers)
        ('ssi_band', c_uint32),     #: Band event (SIGIO)
        ('ssi_overrun', c_uint32),  #: POSIX timer overrun count
        ('ssi_trapno', c_uint32),   #: Trap number that caused signal
        ('ssi_status', c_int32),    #: Exit status or signal (SIGCHLD)
        ('ssi_int', c_int32),       #: Integer sent by sigqueue(2)
        ('ssi_ptr', c_uint64),      #: Pointer sent by sigqueue(2)
        ('ssi_utime', c_uint64),    #: User CPU time consumed (SIGCHLD)
        ('ssi_stime', c_uint64),    #: System CPU time consumed (SIGCHLD)
        ('ssi_addr', c_uint64),     #: Address that generated signal
    ]
    __PADWORDS = 128 - sum(sizeof(field[1]) for
                            field in _FIELDS)

    _fields_ = _FIELDS + [
        ('_pad', c_uint8 * __PADWORDS),  # Pad size to 128 bytes (allow for
                                         # additional fields in the future)
    ]

SIZEOF_SIGNALFD_SIGINFO = sizeof(signalfd_siginfo)
assert SIZEOF_SIGNALFD_SIGINFO == 128


def signalfd_read(sfd):
    """Read signalfd_siginfo data from a signalfd filedescriptor.
    """
    data = os.read(sfd, SIZEOF_SIGNALFD_SIGINFO)
    return signalfd_siginfo.from_buffer_copy(data)
