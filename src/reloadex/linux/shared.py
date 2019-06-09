from reloadex.linux.ctypes_wrappers._eventfd import eventfd, EFD_CLOEXEC, EFD_NONBLOCK

# FIXME: make function, avoid creating at import time
efd_stop_reloader = eventfd(0, flags=EFD_CLOEXEC | EFD_NONBLOCK)