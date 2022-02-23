import cython
from disk import *
import errno
import time
import z3

import random

class DFS(object):

    def __init__(self, disk):
        self.server = Server(disk)
        self._disk = self.server._disk
        self._sb = self.server._disk
        self._imap = self.server._imap

        self.c1 = Client(self.server)
        self.c2 = Client(self.server)

    def lookup(self, parent, name):
        client = random.choice([self.c1, self.c2])
        # debug
        pt = "client is 1!" if client == self.c1 else "client is 2!"
        print(pt)

        return client.c_lookup(parent, name)

    def get_attr(self, ino):
        client = random.choice([self.c1, self.c2])
        # debug
        pt = "client is 1!" if client == self.c1 else "client is 2!"
        print(pt)

        return client.c_get_attr(ino)

    def mknod(parent, name, mode, mtime):
        client = random.choice([self.c1, self.c2])
        # debug
        pt = "client is 1!" if client == self.c1 else "client is 2!"
        print(pt)
        
        return client.c_mknod(parent, name, mode, mtime)

class Client(object):
    
    def __init__(self, server):
        self.server = server
        self.cache = {} # TODO: store info in cache

    def c_lookup(self, parent, name):
        return self.server.s_lookup(parent, name)

    def c_get_attr(self, ino):
        return self.server.s_get_attr(ino)

    def c_mknod(self, parent, name, mode, mtime):
        return self.server.s_mknod(parent, name, mode, mtime)

class Server(object):
    SUPERBLOCK = 0

    SB_OFF_BALLOC = 0
    SB_OFF_IALLOC = 1
    SB_OFF_IMAP = 2

    I_OFF_MTIME = 0
    I_OFF_MODE = 1
    I_OFF_DATA = 4

    # SERVER METHODS
    def __init__(self, disk):
        self._disk = disk

        self._sb = None
        self._imap = None

    def read(self, ino, block):
        #(dani) Nothing seems to change if we comment out the self._begin() (at least in the verification, not sure abt mounting)
        self._begin()
        bid = self._imap[ino]
        r = self._disk.read(bid)

        #(dani) Why commit False here?
        self._commit(False)
        return r

    def _begin(self):
        assert self._sb is None #(dani) commenting out these asserts has no effect on verification
        assert self._imap is None

        self._sb = self._disk.read(self.SUPERBLOCK)
        self._imap = self._disk.read(self._sb[self.SB_OFF_IMAP])

    def _balloc(self):

        #(dani) get index of next available block 
        a = self._sb[self.SB_OFF_BALLOC]
        self._sb[self.SB_OFF_BALLOC] += 1

        # Allocator returned a new block
        assertion(0 < (a + 1))
        
        #(dani) Should we not check some bound for a? Or does the assertion above ensure this alrd?

        return a

    def _ialloc(self):

        #(dani) get index next available inode
        a = self._sb[self.SB_OFF_IALLOC]
        self._sb[self.SB_OFF_IALLOC] += 1

        # we have a free inode...
        #(dani) Note: limited to 512 files (512 entries in the inode mapping block). Removing this assertion leads to an error
        assertion(a < 512)

        return a

    def _commit(self, write=True):
        assert self._sb is not None
        assert self._imap is not None

        if write:
            a = self._balloc()
            self._disk.write(a, self._imap)
            self._disk.flush()
            self._sb[self.SB_OFF_IMAP] = a
            self._disk.write(self.SUPERBLOCK, self._sb)
            self._disk.flush()
        
        #(dani)QUESTION: I don't understand why a commit resets the superblock and inode mapping to None!
        self._sb = None
        self._imap = None

    #(dani) update the inode mapping with the relation (ino -> bid)
    def _set_map(self, ino, bid):
        self._imap[Extract(8, 0, ino)] = bid

    #(dani) Get the block index of inode number ino
    def _get_map(self, ino):
        return self._imap[Extract(8, 0, ino)]

    ########
    #(dani) Given a directory block number and the name of a file within that directory, return the ino of that file
    def dir_lookup(self, blk, name):
        res = -errno.ENOENT

        # In this impl, each dir has <= 2 files. If we change the range here to a larger number, verification still works, tho it takes longer (e.g. 50 files -> 47.5 min to verify single node LFS)
        for i in range(2):
            oname = blk[self.I_OFF_DATA + i * 2]
            oino = blk[self.I_OFF_DATA + i * 2 + 1]

            res = If(And(oname == name, 0 < oino), oino, res)
        return res

    #(dani) Find empty slot in directory
    def dir_find_empty(self, blk):
        res = BitVecVal(-errno.ENOSPC, 64)
        for i in range(2):
            res = If(blk[self.I_OFF_DATA + i * 2] == 0, i, res)
        return res

    def s_get_attr(self, ino):
        s = Stat(0, 0, 0)

       #(dani) OOOHH... Notice that in a lot of operations we start with "begin" and end with "commit". Commit sets the inode mapping & superblock back to None. Investigate more why these two are needed..
        self._begin()

        blk_idx = self._get_map(ino)
        blk = self._disk.read(blk_idx)
        #s.bsize = 0
        s.size = 0
        s.mode = blk[self.I_OFF_MODE]
        s.mtime = blk[self.I_OFF_MTIME]

        self._commit(False)

        return s

    def s_lookup(self, parent, name):
        
        #(dani) same question as in get_attr
        self._begin()

        parent_blkno = self._get_map(parent)
        parent_blk = self._disk.read(parent_blkno)

        ino = self.dir_lookup(parent_blk, name)
        self._commit(False)
        return ino

    def exists(self, parent, name):
        return 0 < self.lookup(parent, name)


    # Given directory inode number ("parent") and a new file name, mode and mtime, create a new file
    def s_mknod(self, parent, name, mode, mtime):

        # check if the file exists 
        #(dani) this seems more to be for semantic help, since it does not really affect the verification (and in many file sys you can indeed create a new file that overwrites an old one of the same name!)
        if self.exists(parent, name):
            assertion(False)
            return BitVecVal(-errno.EEXIST, 64)

        self._begin()

        parent_blkno = self._get_map(parent)
        # (dani) parent_blk is some kind of iterable
        # i think it's a Block data type!
        parent_blk = self._disk.read(parent_blkno) 

        ino = self._ialloc()
        blkno = self._balloc()

        # Finding "end of file"; i.e. where in the dir inode we can write the new file info :)
        eoff = self.dir_find_empty(parent_blk)

        if eoff < 0:
            self._commit(False)
            return eoff

        # write new inode
        inodeblk = ConstBlock(0)

        inodeblk[self.I_OFF_MTIME] = mtime
        inodeblk[self.I_OFF_MODE] = mode
        self._disk.write(blkno, inodeblk)

        # update parent directory
        parent_blk[self.I_OFF_DATA + 2 * Extract(8, 0, eoff)] = name
        parent_blk[self.I_OFF_DATA + 2 * Extract(8, 0, eoff) + 1] = ino

        new_parent_blkno = self._balloc()

        self._disk.write(new_parent_blkno, parent_blk)

        # update the imap
        self._set_map(ino, blkno)
        self._set_map(parent, new_parent_blkno)

        self._commit()

        return ino

    #(dani) QUESTION: I don't understand the crash yet. Also, yggdrasil/diskspec defines several types of disks. Read more about them! this LFS uses AsyncDisk (see below)
    def crash(self, mach):
        return self.__class__(self._disk.crash(mach))


def mkfs(disk):
    sb = disk._disk.read(0)
    if sb[0] == 0:
        sb[DFS.SB_OFF_BALLOC] = 3
        sb[DFS.SB_OFF_IALLOC] = 2
        sb[DFS.SB_OFF_IMAP] = 1
        disk._disk.write(0, sb)

        imap = ConstBlock(0)
        imap[1] = 2
        disk._disk.write(1, imap)


def create_lfs(*args):
    disk = AsyncDisk('/tmp/foo.img')
    dfs = DFS(disk)
    mkfs(dfs)

    return lfs

if __name__ == '__main__':
    dfs = create_dfs()

   # print dfs.lookup(1, 16)
   # print dfs.get_attr(4)
   # print dfs.mknod(1, 20, 2000, 2000)
   # print dfs.lookup(1, 20)
   # print dfs.get_attr(4)
