# A single-node specification 
import errno
from dfs import DFS
from disk import assertion, debug, Stat

from yggdrasil.diskspec import *
from yggdrasil import test

class DFSSpec():
    def __init__(self, mach, dirfn, parentfn, modefn, mtimefn):
        self._mach = mach
        self._dirfn = dirfn
        self._modefn = modefn
        self._mtimefn = mtimefn
        self._parentfn = parentfn

    # In the implementation, lookup results can be cached (this should not affect consistentcy since we do not delete files)
    #def lookup(self, parent, name):
    def lookup(self, cid, parent, name):
        ino = self._dirfn(parent, name)
        return If(0 < ino, ino, -errno.ENOENT)

    # In the implementation, attributes can be cached by clients. Now, this could lead to consistency errors! 
    # One option to prevent inconsitencies is to first access the "last modified time" from the disk, and
    # if this time matches the time of the attributes stored on cache, then we know those attributes are all valid
    #def get_attr(self, ino):
    def get_attr(self,cid, ino):
        return Stat(size=0,
                    mode=self._modefn(ino),
                    mtime=self._mtimefn(ino))

    #def mknod(self, parent, name, mode, mtime):
    def mknod(self, cid, parent, name, mode, mtime):

        if 0 < self.lookup(parent, name):
            return BitVecVal(-errno.EEXIST, 64)
        
        on = self._mach.create_on([])

        ino = FreshBitVec('ino', 64)
        assertion(0 < ino)
        assertion(Not(0 < self._parentfn(ino)))
        
        self._dirfn = self._dirfn.update((parent, name), ino, guard=on)
        self._modefn = self._modefn.update(ino, mode, guard=on)
        self._mtimefn = self._mtimefn.update(ino, mtime, guard=on)
        self._parentfn = self._parentfn.update(ino, parent, guard=on)

        return ino

    # For now, ignore size
    #def set_attr(self, ino, size, mode,  mtime):
    #    self._modefn = self._modefn.update(ino, mode, guard = on)
    #    self._mtimefin = self._mtimefn.update(ino, mtime, guard = on)

    # TODO: write and read
    # def write(self, ino, offset, count, data): 
        

    # def read(self, ino, offset, count):


    def crash(self, mach):
        return self.__class__(mach, self._dirfn, self._parentfn, self._modefn, self._mtimefn)

    
class DFSRefinement(test.RefinementTest):
    def create_spec(self, mach):
        dirfn = FreshUFunction('dirfn', SizeSort, SizeSort, SizeSort)
        parentfn =  FreshUFunction('parentfn', SizeSort, SizeSort)
        modefn =  FreshUFunction('modefn', SizeSort, SizeSort)
        mtimefn =  FreshUFunction('mtimefn', SizeSort, SizeSort)
        return DFSSpec(mach, dirfn, parentfn, modefn, mtimefn)

    def create_impl(self, mach):
        array = FreshDiskArray('disk')
        disk = AsyncDisk(mach, array)
        return DFS(disk)

    def pre_post(self, spec, impl, **kwargs):       
        name = FreshBitVec('name.pre', 64)
        parent = BitVecVal(1, 64)
       
        # client id
        cid = FreshBitVec('cid', 64)

        sb = impl._disk.read(0)
        imap = impl._disk.read(sb[2])
        off = FreshBitVec("off", 9)

        pre = ForAll([cid], (ForAll([name], Implies(name != 0, And(
            Implies(0 < spec._dirfn(parent, name),
                    parent == spec._parentfn(spec._dirfn(parent, name))),

            Implies(0 < impl.lookup(cid, parent, name),
                    And(impl.lookup(cid, parent, name) < sb[1],
                        spec.get_attr(spec.lookup(cid, parent, name)) == impl.get_attr(cid, impl.lookup(cid, parent, name)))),

            spec.lookup(cid,  parent, name) == impl.lookup(cid, parent, name))))))


        #(dani) QUESTION: CHECK WHAT THIS DOES!!! 
        pre = And(pre, 
                  ForAll([off], Implies(ZeroExt(64 - off.size(), off) < sb[1],
                                        And(0 < imap[off], imap[off] < sb[0]))))

        pre = And(pre,
                # allocated blocks are in range ]0..allocator[
                #0 < sb[DFS.SB_OFF_IMAP], sb[DFS.SB_OFF_IMAP] < sb[DFS.SB_OFF_BALLOC],
                #0 < imap[1], imap[1] < sb[DFS.SB_OFF_BALLOC],
                0 < sb[2], sb[2] < sb[0],
                0 < imap[1], imap[1] < sb[0],

                # root dir inode has been allocated
                #1 < sb[DFS.SB_OFF_IALLOC]
                1 < sb[1],
                )
            
        #(dani) QUESTION: see what this yield function does
        # (spec, impl, (_, name0, _, _), (sino, iino)) = yield pre   
        (spec, impl, (cid0, _, name0, _, _), (sino, iino)) = yield pre   


        #print(self.show(pre))
        self.show(pre)

        if iino < 0:
            iino = impl.lookup(cid0, parent, name0)

        if self._solve(sino == iino):
            assertion(sino == iino)

        sb = impl._disk.read(0)
        imap = imp._disk.read(sb[2])

        post = ForAll([cid], (ForAll([name], Implies(name != 0, And(
            Implies(0 < spec._dirfn(parent, name),
                    parent == spec._parentfn(spec._dirfn(parent, name))),

            Implies(0 < impl.lookup(cid, parent, name),
                    And(impl.lookup(cid, parent, name) < sb[1],
                        spec.get_attr(cid, spec.lookup(parent, name)) == impl.get_attr(cid, impl.lookup(cid, parent, name)))),

            spec.lookup(cid, parent, name) == impl.lookup(cid, parent, name))))))


        #(dani) QUESTION: CHECK WHAT THIS DOES!!! 
        post = And(post, 
                  ForAll([off], Implies(ZeroExt(64 - off.size(), off) < sb[1],
                                        And(0 < imap[off], imap[off] < sb[0]))))


        post = And(post,
                # allocated blocks are in range ]0..allocator[
                #0 < sb[DFS.SB_OFF_IMAP], sb[DFS.SB_OFF_IMAP] < sb[DFS.SB_OFF_BALLOC],
                #0 < imap[1], imap[1] < sb[DFS.SB_OFF_BALLOC],
                0 < sb[2], sb[2] < sb[0],
                0 < imap[1], imap[1] < sb[0],


                # root dir inode has been allocated
                #1 < sb[DFS.SB_OFF_IALLOC]
                1 < sb[1],
                )

        yield post

    def match_mknod(self):
        parent = BitVecVal(1, 64)
        name = FreshBitVec('name', 64)
        mode = FreshBitVec('mode', 64)
        mtime = FreshBitVec('mtime', 64)
        assertion(name != 0)
        #yield (parent, name, mode, mtime)
        # new
        cid = FreshBitVec('cid', 64)
        yield (cid, parent, name, mode, mtime)

if __name__ == '_main_':
    test.main()

