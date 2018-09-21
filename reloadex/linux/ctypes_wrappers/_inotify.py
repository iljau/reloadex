import os
import struct
from collections import namedtuple
from ctypes import *
from typing import Iterator

from reloadex.linux.ctypes_wrappers.common import libc, error_text

__all__ = [
    "IN_CLOEXEC",
    "IN_NONBLOCK",
    "inotify_init1",
    "inotify_add_watch",

    "inotify_event",
    "SIZEOF_INOTIFY_EVENT",
    "NAME_MAX",
    "INOTIFY_MAX_EVENT_SIZE",

    "get_events",

    "IN_ACCESS",
    "IN_MODIFY",
    "IN_ATTRIB",
    "IN_CLOSE_WRITE",
    "IN_CLOSE_NOWRITE",
    "IN_CLOSE",
    "IN_OPEN",
    "IN_MOVED_FROM",
    "IN_MOVED_TO",
    "IN_MOVE",
    "IN_CREATE",
    "IN_DELETE",
    "IN_DELETE_SELF",
    "IN_MOVE_SELF",
    
    "IN_UNMOUNT",
    "IN_Q_OVERFLOW",
    "IN_IGNORED",

    "IN_ONLYDIR",
    "IN_DONT_FOLLOW",
    "IN_EXCL_UNLINK",
    "IN_MASK_ADD",
    "IN_ISDIR",
    "IN_ONESHOT",

    "IN_ALL_EVENTS",

    "inotify_read"
]


IN_NONBLOCK = os.O_NONBLOCK
IN_CLOEXEC = os.O_CLOEXEC

inotify_init1 = libc.inotify_init1
inotify_init1.argtypes = [c_int]
def res_inotify_init1(fd):
    if fd == -1:
        errno = get_errno()
        raise OSError(errno, error_text(errno))
    assert fd >= 0
    return fd
inotify_init1.restype = res_inotify_init1


# extern int inotify_add_watch (int __fd, const char *__name, uint32_t __mask)
inotify_add_watch = libc.inotify_add_watch
inotify_add_watch.argtypes = [c_int, c_char_p, c_uint32]
def res_inotify_add_watch(fd):
    if fd == -1:
        errno = get_errno()
        raise OSError(errno, error_text(errno))
    assert fd >= 0
    return fd
inotify_add_watch.restype = res_inotify_add_watch

# struct inotify_event
# {
#   int wd;		/* Watch descriptor.  */
#   uint32_t mask;	/* Watch mask.  */
#   uint32_t cookie;	/* Cookie to synchronize two events.  */
#   uint32_t len;		/* Length (including NULs) of name.  */
#   char name __flexarr;	/* Name.  */
# };
class inotify_event(Structure):
    _fields_ = [
          ("wd", c_int)
        , ("mask", c_uint32)
        , ("cookie", c_uint32)
        , ("len", c_uint32)
    ]

# should be 16
SIZEOF_INOTIFY_EVENT = sizeof(inotify_event)
assert SIZEOF_INOTIFY_EVENT == 16, "%d != 16" % SIZEOF_INOTIFY_EVENT

NAME_MAX = 255
INOTIFY_MAX_EVENT_SIZE = sizeof(inotify_event) + NAME_MAX + 1

_InofityEvent = namedtuple("_InofityEvent", ["wd", "mask", "cookie", "name"])


def get_events(event_buffer) -> Iterator[_InofityEvent]:
    i = 0
    while i + 16 <= len(event_buffer):
        wd, mask, cookie, length = struct.unpack_from('iIII', event_buffer, i)
        name = event_buffer[i + 16:i + 16 + length].rstrip(b'\0')
        i += 16 + length
        yield _InofityEvent(wd, mask, cookie, name)

##

# /* Supported events suitable for MASK parameter of INOTIFY_ADD_WATCH.  */
IN_ACCESS	    = 0x00000001	#/* File was accessed.  */
IN_MODIFY	    = 0x00000002	#/* File was modified.  */
IN_ATTRIB	    = 0x00000004	#/* Metadata changed.  */
IN_CLOSE_WRITE	= 0x00000008	#/* Writtable file was closed.  */
IN_CLOSE_NOWRITE= 0x00000010	#/* Unwrittable file closed.  */
IN_CLOSE	    = (IN_CLOSE_WRITE | IN_CLOSE_NOWRITE) #/* Close.  */
IN_OPEN		    = 0x00000020	#/* File was opened.  */
IN_MOVED_FROM	= 0x00000040	#/* File was moved from X.  */
IN_MOVED_TO     = 0x00000080	#/* File was moved to Y.  */
IN_MOVE		    = (IN_MOVED_FROM | IN_MOVED_TO) #/* Moves.  */
IN_CREATE	    = 0x00000100	#/* Subfile was created.  */
IN_DELETE	    = 0x00000200	#/* Subfile was deleted.  */
IN_DELETE_SELF	= 0x00000400	#/* Self was deleted.  */
IN_MOVE_SELF	= 0x00000800	#/* Self was moved.  */

# /* Events sent by the kernel.  */
IN_UNMOUNT	    = 0x00002000	#/* Backing fs was unmounted.  */
IN_Q_OVERFLOW   = 0x00004000	#/* Event queued overflowed.  */
IN_IGNORED	    = 0x00008000	#/* File was ignored.  */

#/* Helper events.  */
#IN_CLOSE	    = (IN_CLOSE_WRITE | IN_CLOSE_NOWRITE)	#/* Close.  */
#IN_MOVE	        = (IN_MOVED_FROM | IN_MOVED_TO)		#/* Moves.  */

#/* Special flags.  */
IN_ONLYDIR	    = 0x01000000	#/* Only watch the path if it is a directory.  */
IN_DONT_FOLLOW	= 0x02000000	#/* Do not follow a sym link.  */
IN_EXCL_UNLINK	= 0x04000000	#/* Exclude events on unlinked objects.  */
IN_MASK_ADD	    = 0x20000000	#/* Add to the mask of an already existing watch.  */
IN_ISDIR	    = 0x40000000	#/* Event occurred against dir.  */
IN_ONESHOT	    = 0x80000000	#/* Only send event once.  */

# /* All events which a program can wait on.  */
IN_ALL_EVENTS	= (IN_ACCESS | IN_MODIFY | IN_ATTRIB | IN_CLOSE_WRITE  \
			  | IN_CLOSE_NOWRITE | IN_OPEN | IN_MOVED_FROM	      \
			  | IN_MOVED_TO | IN_CREATE | IN_DELETE		      \
			  | IN_DELETE_SELF | IN_MOVE_SELF)


def inotify_read(fd) -> Iterator[_InofityEvent]:
    event_buffer = os.read(fd, INOTIFY_MAX_EVENT_SIZE * 2048)
    yield from get_events(event_buffer)