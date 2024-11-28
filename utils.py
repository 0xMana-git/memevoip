import os, errno
import threading
def remove_silent(filename):
    try:
        os.remove(filename)
    except OSError as e: # this would be "except OSError, e:" before Python 2.6
        if e.errno != errno.ENOENT: # errno.ENOENT = no such file or directory
            raise # re-raise exception if a different error occurred


def open_with_flag(fpath, os_flag, fd_open_flag):
    return os.fdopen(os.open(fpath, os_flag), fd_open_flag)
def mkfifo_open(fpath, os_flag, fd_open_flag):
    os.mkfifo(fpath, 0o600)
    return open_with_flag(fpath, os_flag, fd_open_flag)
    

def start_daemon_thread(target, args=()):
    t = threading.Thread(target=target, args=args)
    t.daemon = True
    t.start()
    return t



def make_addr_key(addr): 
    return str(addr).replace("'", "_").replace(" ", "_").replace(",", "_").replace("(", "_").replace(")", "_")
