from ctypes import *

from reloadex.linux.ctypes_wrappers.common import libc, error_text

__all__ = [
    "POSIX_SPAWN_USEVFORK",
    "posix_spawnattr_t",
    "posix_spawnattr_init",
    "posix_spawnattr_setflags",
    "posix_spawn",
    "create_char_array"
]

POSIX_SPAWN_USEVFORK = 0x40


class sigset_t(Structure):
    NWORDS = int(1024 / (8 * sizeof(c_ulong)))

    _fields_ = (
        ('__val', c_ulong * NWORDS),
    )


class sched_param(Structure):
    _fields_ = (
        ('sched_priority', c_int),
    )


class posix_spawnattr_t(Structure):
    _fields_ = [
          ("__flags", c_short)
        , ("__pgrp", c_int) # pid_t
        , ("__sd", sigset_t) # pid_t
        , ("__ss", sigset_t) # pid_t
        , ("__sp", sched_param) # pid_t
        , ("__policy", c_int) # pid_t
        , ("__pad", c_int * 16) # pid_t
    ]

# should be: 336
# size = ctypes.sizeof(posix_spawnattr_t)
# print("size", size)

def res_posix_spawn_fns(errno):
    if errno != 0:
        raise OSError(errno, error_text(errno))
    return errno

posix_spawnattr_init = libc.posix_spawnattr_init
posix_spawnattr_init.argtypes = [POINTER(posix_spawnattr_t)]
posix_spawnattr_init.restype = c_int
posix_spawnattr_init.restype = res_posix_spawn_fns


posix_spawnattr_destroy = libc.posix_spawnattr_destroy
posix_spawnattr_destroy.argtypes = [POINTER(posix_spawnattr_t)]
posix_spawnattr_destroy.restype = res_posix_spawn_fns

posix_spawnattr_setflags = libc.posix_spawnattr_setflags
posix_spawnattr_setflags.argtypes = [POINTER(posix_spawnattr_t), c_short]
posix_spawnattr_setflags.restype = res_posix_spawn_fns

##

LP_c_char = POINTER(c_char)
LP_LP_c_char = POINTER(LP_c_char)

posix_spawn = libc.posix_spawn
posix_spawn.argtypes = [POINTER(c_int),
    c_char_p,
    c_void_p,
    POINTER(posix_spawnattr_t),
    LP_LP_c_char,
    LP_LP_c_char
]
posix_spawn.restype = res_posix_spawn_fns


# https://mail.python.org/pipermail/python-list/2016-June/709889.html
def create_char_array(_args):
    argc = len(_args)
    argv = (LP_c_char * (argc + 1))()
    for i, arg in enumerate(_args):
        enc_arg = arg.encode('utf-8')
        argv[i] = create_string_buffer(enc_arg)
    return argv
