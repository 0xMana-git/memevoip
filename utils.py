import os, errno

def remove_silent(filename):
    try:
        os.remove(filename)
    except OSError as e: # this would be "except OSError, e:" before Python 2.6
        if e.errno != errno.ENOENT: # errno.ENOENT = no such file or directory
            raise # re-raise exception if a different error occurred



def mkfifo(fpath, open_mode, do_open=True):
    os.mkfifo(fpath, 0o600)
    fmode = "rb"
    if(open_mode == os.O_WRONLY):
        fmode = "wb"
    if do_open:
        return os.fdopen(os.open(fpath, os.O_NONBLOCK | open_mode), fmode)
    

def open_with_flag(fpath, os_flag, fd_open_flag):
    return os.fdopen(os.open(fpath, os_flag), fd_open_flag)\

def make_addr_key(addr): 
    return str(addr).replace("'", "_").replace(" ", "_").replace(",", "_").replace("(", "_").replace(")", "_")
