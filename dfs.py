import cython
from disk import *
import errno
import time
import z3

import random
import pdb

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
        # debugging
        pt = "client is 1!" if client == self.c1 else "client is 2!"
        print(pt)

        return client.c_lookup(parent, name)

    def get_attr(self, ino):
        client = random.choice([self.c1, self.c2])
        # debugging
        pt = "client is 1!" if client == self.c1 else "client is 2!"
        print(pt)

        return client.c_get_attr(ino)

    def mknod(self, parent, name, mode, mtime):
        client = random.choice([self.c1, self.c2])
        # debugging
        pt = "client is 1!" if client == self.c1 else "client is 2!"
        print(pt)
        
        return client.c_mknod(parent, name, mode, mtime)

    def crash(self, mach):
        return self.__class__(self._disk.crash(mach))


class Client(object):
    
    def __init__(self, server):
        self.server = server
        self._disk = self.server._disk
        self.cache = Dict()# TODO: store info in cache

    def _set_cache(self, key, val):
        self.cache.__setitem__(key, val)
        return val
   
    def _get_cache(self, key):
        if self.cache.has_key(key):
            return self.cache.get(key, BitVecVal(-1, 64))
        return BitVecVal(-1, 64)

    # TODO: use KVImpl for cache instead!
    def c_lookup(self, parent, name):
        #ino_opt = self._get_cache(name)
        #if ino_opt > 0:
        #    return ino_opt
        ino = self.server.s_lookup(parent, name)
        self._set_cache((self, parent), ino)
        return ino

    def c_get_attr(self, ino):
        return self.server.s_get_attr(ino)

    def c_mknod(self, parent, name, mode, mtime):
        return self.server.s_mknod(parent, name, mode, mtime)

    def c_set_attr(self, ino, stat):
        return self.server.s_set_attr(ino, stat)

    def c_set_time(self, ino, mtime):
        stat = self.c_get_attr(ino)
        stat.mtime = mtime
        return self.c_set_attr(ino, stat)



class Server(object):
    SUPERBLOCK = 0

    SB_OFF_BALLOC = 0
    SB_OFF_IALLOC = 1
    SB_OFF_IMAP = 2

    I_OFF_MTIME = 0
    I_OFF_MODE = 1
    I_OFF_DATA = 4

    # new
    # this will allow each dir to have up to 20 files (later: distinguish between file/dir)
    I_OFF_PTR = 24 

    def __init__(self, disk):
        self._disk = disk

        self._sb = None
        self._imap = None

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
        return a

    def _ialloc(self):

        #(dani) get index next available inode
        a = self._sb[self.SB_OFF_IALLOC]
        self._sb[self.SB_OFF_IALLOC] += 1

        # we have a free inode...
        #(dani) Note: limited to 512 files (512 entries in the inode mapping block).
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

        # I think begin() and commit() are a way of ensuring atomicity
        self._begin()

        blk_idx = self._get_map(ino)
        blk = self._disk.read(blk_idx)
        s.size = 0
        s.mode = blk[self.I_OFF_MODE]
        s.mtime = blk[self.I_OFF_MTIME]

        self._commit(False)
        return s
    
    def s_set_attr(self, ino, stat):
        self._begin()

        blkno = self._get_map(ino)
        blk = self._disk.read_inoblk(blkno)
        blk[self.I_OFF_MODE] = stat.mode
        blk[self.I_OFF_MTIME] = stat.mtime
        self._disk.write(blkno, blk)

        self._commit(False)
        return stat



    def s_lookup(self, parent, name):
        
        #(dani) same question as in get_attr
        self._begin()

        parent_blkno = self._get_map(parent)
        parent_blk = self._disk.read(parent_blkno)

        ino = self.dir_lookup(parent_blk, name)
        self._commit(False)
        return ino

    def exists(self, parent, name):
        return 0 < self.s_lookup(parent, name)


    def s_mknod(self, parent, name, mode, mtime):

        # check if the file exists 
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
        inodeblk[self.I_OFF_PTR] = -1
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

    def write(self, ino, data):
        self._begin()

        # allocate new block
        blkno = self._balloc()

        # write data
        datablk = ConstBlock(0)
        self._disk.write(blkno, data)

        # update inode
        inoblkno = self._get_map(ino)
        inoblk = self._disk.read(inoblkno)
        inoblk[self.I_OFF_PTR] = blkno
        self._disk.write(inoblkno, inoblk)

        self._commit()
        return blkno

    def read_file(self, ino):
        self._begin()
        
        blkno = self._imap[ino]
        inoblk = self._disk.read(blkno)
            
        # Nothing has been written
        if inoblk[self.I_OFF_PTR] == -1:
            return ""

        data_addr = inoblk[self.I_OFF_PTR]
        r = self._disk.read(data_addr)
        
        self._commit(False)
        return r

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

def create_dfs(*args):
    disk = AsyncDisk('/tmp/foo.img')
    dfs = DFS(disk)
    mkfs(dfs)

    return dfs

if __name__ == '__main__':
    dfs = create_dfs()

   # print dfs.lookup(1, 16)
   # print dfs.get_attr(4)
   # print dfs.mknod(1, 20, 2000, 2000)
   # print dfs.lookup(1, 20)
   # print dfs.get_attr(4)
