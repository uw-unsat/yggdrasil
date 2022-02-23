import cython
from disk import *
import errno
import time
import z3

# new
from yggdrasil.diskspec import *
from yggdrasil import test

class LFS(object):
    
    #(dani) Index where the superblock is located in "array" of blocks that composes our file sys. i.e., sb is the very first block
    SUPERBLOCK = 0
    
    #(dani) Index where the "next available block index" is stored WITHIN the superblock. This will be initialised to 3
    SB_OFF_BALLOC = 0

    #(dani) Index where the next available inode number is stored within the superblock. Initialised to 2 (root is ino 1).
    SB_OFF_IALLOC = 1

    #(dani) Index where the "inode mapping" is initially stored withing the file sys (the location of this mapping moves each time we mknod).
    # Initially, this block will have one entry, 1 -> b1, since the root inode is initially stored in the second block (index 1)
    SB_OFF_IMAP = 2

    #(dani) Index where mtime is stored within an inode block
    I_OFF_MTIME = 0
    #(dani) Index where mode is stored within an inode block #QUESTION: what even is mode in an lfs?
    I_OFF_MODE = 1

    #(dani) It seems like this is the offset where we can write (ino, name) pairings in directory inodes
    I_OFF_DATA = 4 
    
    # (dani) If we implement WRITING/READING, then define also an I_OFF_PTR(S), which is the offset where data block pointer(s) are located in each inode.
    # This offset should always be after the latest possible I_OFF_DATA. So, define the max number of files in a dir (in the dir_lookup and dir_find_empty operations below)
    # and then I_OFF_PTR = I_OFF_DATA + max
    # BUT ALSO: maybe we should differentiate between files and dirs? In which case, I_OFF_DATA would be the same for both, but how we use them (i.e. inode mappings if a dir or storing ptrs to data in case a file) would differ!
    
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
        assert self._sb is None #(dani) commenting out these asserts has no effect
        assert self._imap is None

        self._sb = self._disk.read(self.SUPERBLOCK)
        self._imap = self._disk.read(self._sb[self.SB_OFF_IMAP])

    def _balloc(self):

        #(dani) get index of next available block 
        a = self._sb[self.SB_OFF_BALLOC]
        self._sb[self.SB_OFF_BALLOC] += 1

        # Allocator returned a new block
        assertion(0 < (a + 1))
        
        #(dani) Should we not check that a < 512? 
        # QUESTION: I added the assertion and verification still worked. Now I wonder why verification works without the assertion...
        # On the other hand, removing the (a < 512) assertion for _ialloc causes errors!
        # ok, I think I figured out why this happens... There is only space for 512 entries in the inode mapping (one block), but there are much more than 512 blocks in the file system!

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

        # I'm confused here... Does this mean each directory can have at most 2 files? note: if I change the range here to a larger number, verification still works, tho it takes longer (e.g. 50 files -> 47.5 min to verify)
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

    def get_attr(self, ino):
        s = Stat(0, 0, 0)

        #(dani) QUESTION: why do we need to _begin() every time we get_attr?? An error is thrown by Z3 if we comment out the code below.
        #(dani) I understand we need to initialise the inode mapping and superblock. But what if this has already been done?
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

    def lookup(self, cid, parent, name):
        
        #(dani) same question as in get_attr
        self._begin()

        parent_blkno = self._get_map(parent)
        parent_blk = self._disk.read(parent_blkno)

        ino = self.dir_lookup(parent_blk, name)
        self._commit(False)
        return ino

    def exists(self, parent, name):
        cid = FreshBitVec("cid", 64)
        return 0 < self.lookup(cid, parent, name)


    # Given directory inode number ("parent") and a new file name, mode and mtime, create a new file
    def mknod(self, parent, name, mode, mtime):

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
        sb[LFS.SB_OFF_BALLOC] = 3
        sb[LFS.SB_OFF_IALLOC] = 2
        sb[LFS.SB_OFF_IMAP] = 1
        disk._disk.write(0, sb)

        imap = ConstBlock(0)
        imap[1] = 2
        disk._disk.write(1, imap)


def create_lfs(*args):
    disk = AsyncDisk('/tmp/foo.img')
    lfs = LFS(disk)
    mkfs(lfs)

    return lfs

if __name__ == '__main__':
    lfs = create_lfs()

    print lfs.lookup(1, 16)
    print lfs.get_attr(4)
    print lfs.mknod(1, 20, 2000, 2000)
    print lfs.lookup(1, 20)
    print lfs.get_attr(4)
