from ctypes import *

from reloadex.linux.ctypes_wrappers._signalfd import sigset_t
from reloadex.linux.ctypes_wrappers.common import libc, error_text

__all__ = [
    "POSIX_SPAWN_RESETIDS",
    "POSIX_SPAWN_SETPGROUP",
    "POSIX_SPAWN_SETSIGDEF",
    "POSIX_SPAWN_SETSIGMASK",
    "POSIX_SPAWN_SETSCHEDPARAM",
    "POSIX_SPAWN_SETSCHEDULER",
    "POSIX_SPAWN_USEVFORK",
    "POSIX_SPAWN_SETSID",

    "posix_spawnattr_t",
    "posix_spawnattr_init",
    "posix_spawnattr_setflags",
    "posix_spawn",

    "posix_spawnattr_setsigdefault",
    "posix_spawnattr_setsigmask",

    "create_char_array",
]

POSIX_SPAWN_RESETIDS        = 0x01
POSIX_SPAWN_SETPGROUP       = 0x02
POSIX_SPAWN_SETSIGDEF       = 0x04
POSIX_SPAWN_SETSIGMASK      = 0x08
POSIX_SPAWN_SETSCHEDPARAM   = 0x10
POSIX_SPAWN_SETSCHEDULER    = 0x20

#ifdef __USE_GNU
POSIX_SPAWN_USEVFORK        = 0x40
POSIX_SPAWN_SETSID          = 0x80
#endif


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


posix_spawnp = libc.posix_spawnp
posix_spawnp.argtypes = [POINTER(c_int),
    c_char_p,
    c_void_p,
    POINTER(posix_spawnattr_t),
    LP_LP_c_char,
    LP_LP_c_char
]
posix_spawnp.restype = res_posix_spawn_fns

# https://mail.python.org/pipermail/python-list/2016-June/709889.html
def create_char_array(_args):
    argc = len(_args)
    argv = (LP_c_char * (argc + 1))()
    for i, arg in enumerate(_args):
        enc_arg = arg.encode('utf-8')
        argv[i] = create_string_buffer(enc_arg)
    return argv

# extern int posix_spawnattr_setsigmask (posix_spawnattr_t *__restrict __attr,
# 				       const sigset_t *__restrict __sigmask)

posix_spawnattr_setsigmask = libc.posix_spawnattr_setsigmask
posix_spawnattr_setsigmask.argtypes = [POINTER(posix_spawnattr_t), POINTER(sigset_t)]
posix_spawnattr_setsigmask.restype = res_posix_spawn_fns

# /* Set signal mask for signals with default handling in ATTR to SIGDEFAULT.  */
# extern int posix_spawnattr_setsigdefault (posix_spawnattr_t *__restrict __attr,
# 					  const sigset_t *__restrict
# 					  __sigdefault)

posix_spawnattr_setsigdefault = libc.posix_spawnattr_setsigdefault
posix_spawnattr_setsigdefault.argtypes = [POINTER(posix_spawnattr_t), POINTER(sigset_t)]
posix_spawnattr_setsigdefault.restype = res_posix_spawn_fns