import cython
from disk import *
import errno
import time
from z3 import *

import random
from kvimpl import KVImpl
from yggdrasil.util import fresh_name, SizeSort
from yggdrasil.ufarray import Block, StringElementSort #, FreshBlock


class DFS(object):
    def __init__(self, disk):
        self.server = Server(disk)
        self._disk = self.server._disk
        self._sb = self.server._sb
        self._imap = self.server._imap

        self.c1 = Client(self.server)
        self.c2 = Client(self.server)

    def lookup(self, parent, name):
        # TODO: define a better lookup (union?). Or maybe keep this as is, and change the way we do the verification?
        self._begin()
        client = random.choice([self.c1, self.c2])
        # debugging
        #pt = "client is 1!" if client == self.c1 else "client is 2!"; print(pt)
        res = client.c_lookup(parent, name)
        self._commit(False)
        return res

    def get_attr(self, ino):
        client = random.choice([self.c1, self.c2])
        # debugging
        #pt = "client is 1!" if client == self.c1 else "client is 2!"; print(pt)

        return client.c_get_attr(ino)

    def mknod(self, parent, name, mode, mtime):
        client = random.choice([self.c1, self.c2])
        # debugging
        #pt = "client is 1!" if client == self.c1 else "client is 2!"; print(pt)
        
        return client.c_mknod(parent, name, mode, mtime)

    def crash(self, mach):
        return self.__class__(self._disk.crash(mach))

    def _begin(self):
        assert self._sb is None 
        assert self._imap is None

        self._sb = self._disk.read(self.server.SUPERBLOCK)
        self._imap = self._disk.read(self._sb[self.server.SB_OFF_IMAP])

    def _balloc(self):
        #(dani) get index of next available block 
        a = self._sb[self.server.SB_OFF_BALLOC]
        self._sb[self.server.SB_OFF_BALLOC] += 1

        # Allocator returned a new block
        assertion(0 < (a + 1))
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

    #def read(self, ino, off):
    #    # TODO: write client interface for read
    #    return self.server.read(ino, off) 
    
    def read(self, ino):
        # TODO: write client interface for read
        return self.server.read(ino) 
    
    def write(self, ino, data):
        return self.server.s_write(ino, data)

class Client(object):
    
    def __init__(self, server):
        self.server = server
        self._disk = self.server._disk 
        
        # TODO: store more info in cache
        self._cache = Dict()

    def _set_cache(self, key, val):
        self._cache[key] = val
        #return val
   
    def c_lookup(self, parent, name):
       # print("looking up name", name, "of parent", parent)
        ino_opt = self._cache.get((parent, name), BitVecVal(-1, 64)) # ok

#        Tests: if either of these hold, then the If statement below always chooses one path, which should not happen!
#        assertion(UGT(ino_opt, BitVecVal(0, 64)))
#        assertion(Not(UGT(ino_opt, BitVecVal(0, 64))))
            
        return If(UGT(ino_opt, BitVecVal(-1, 64)), ino_opt, self.c_lookup_server(parent, name))

    def c_lookup_server(self, parent, name):
        #print("we had to contact the disk!!")
        ino = self.server.s_lookup(parent, name)
        self._set_cache((parent, name), ino)
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

    def c_write(self, ino, mtime, data):
        pass


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
        # TODO: uncomment
        #assert self._sb is None 
        #assert self._imap is None

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

        # (dani) In this impl, each dir has <= 2 files. If we change the range here to a larger number, verification still works, tho it takes longer (e.g. 50 files -> 47.5 min to verify single node LFS)
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

        # begin() and commit() are a way of ensuring atomicity (acho)
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
        parent_blk = self._disk.read(parent_blkno) 

        ino = self._ialloc()
        blkno = self._balloc()

        # Finding "end of directory"; i.e. where in the dir inode we can write the new file info :)
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

        # NEW: Allocate block for file's contents (initially empty)
        datablkno = self._balloc()
        datablk = ConstBlock(0) # TODO: change this for something else???
        self._disk.write(datablkno, datablk)
        inodeblk[self.I_OFF_PTR] = datablkno

        self._commit()

        return ino

    # Write a block to an existing file
    def s_write(self, ino, datablk):

        self._begin()
        print("a write!!!!!!!!!!!!!")
        if 0 > ino:
            return BitVecVal(-errno.ENOENT, 64)
    
        # get location of file's content block
        inodeblk = self._disk.read(ino)
        datablkptr = inodeblk[self.I_OFF_PTR]
            
        # write block
        self._disk.write(datablkptr, datablk)
        self._commit()

    # TODO: cache reads
    # Read contents of a file the ino points to, if any
   # def read(self, ino, off):
    def read(self, ino):
        self._begin()
        if 0 > ino:
            #return BitVecVal(-errno.ENOENT, 64)
            return ConstBlock(0)

        blkno = self._get_map(ino)
        inoblk = self._disk.read(blkno)        
        data_addr = inoblk[self.I_OFF_PTR]
        assertion(data_addr >= 0)
        blk = self._disk.read(data_addr)

        self._commit(False)
        
#        return blk[off]
        return blk

        # Idea: instead of always allocating a content block in mknod (a content block which may end up not being used, which is wasteful), we can find a way of keeping track of whether the file has been written to (for example, by the value stored in inode[self.I_OFF_PTR]), and, depending on that value, output a block that was read or a ConstBlock(0)
        # for an example of this, see the read fn in "dirinode.py": res = If(And(is_mapped, ULT(blocknum, bsize)), res, ConstBlock(0))
        # another idea: since each file only has one data block so far, maybe we can just write the data in the inode itself?

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


# NOTE ON WRITE: The inode update is not done in the usual log-structured way. In a typical LFS, we would create a new inode with the new information and then create a new inode mapping with the new, updated information. Here, the inode block and inode mapping block remain the same, and we simply write to them. This can be changed later. Also, it seems that the LFS implementation by the yggdrasil team also does not write a new inode mapping when updating the mapping (check).

# Note on s_lookup: even though the dfs lookup in wrapped in a transaction, s_lookup (which is called by dfs' lookup) also has to be in a transaction or else verification fails! Isn't this odd. I thought transactions would recursrively apply to called functions

# Sketches: 
# transaction for clients:
#    def _begin(self):
#        assert self.server._sb is None 
#        assert self.server._imap is None
#
#        self._sb = self._disk.read(self.server.SUPERBLOCK)
#        self._imap = self._disk.read(self.server._sb[self.server.SB_OFF_IMAP])
#
#    def _commit(self, write=True):
#        assert self._sb is not None
#        assert self._imap is not None
#
#        if write:
#            a = self._balloc()
#            self._disk.write(a, self._imap)
#            self._disk.flush()
#            self._sb[self.server.SB_OFF_IMAP] = a
#            self._disk.write(self.server.SUPERBLOCK, self.server._sb)
#            self._disk.flush()
#        
#        self.server._sb = None
        
# OLD WRITE
# write data
#for i in range(data):
#            datablk[i] = data[i]
#        self.server._imap = None

# NOTE: right now this is not an ideal implementation. Server should be STATELESS, so clients should given the ino directly. Chnage this to make it a client call, where the client looks up. Actually, not sure, go check nfs documentation... TODO

