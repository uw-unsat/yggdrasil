# A single-node specification 
import errno
from dfs import DFS
from dfs_spec import DFSSpec
from disk import assertion, debug, Stat

from yggdrasil.diskspec import *
from yggdrasil import test
from kvimpl import KVImpl

class DFSRefinement(test.RefinementTest):
    def create_spec(self, mach):
        dirfn = FreshUFunction('dirfn', SizeSort, SizeSort, SizeSort)
        parentfn =  FreshUFunction('parentfn', SizeSort, SizeSort)
        modefn =  FreshUFunction('modefn', SizeSort, SizeSort)
        mtimefn =  FreshUFunction('mtimefn', SizeSort, SizeSort)
#        datafn = FreshUFunction('datafn', SizeSort, BlockSort)
        datafn = FreshDiskArray('datafn')
        return DFSSpec(mach, dirfn, parentfn, modefn, mtimefn, datafn)

    def create_impl(self, mach):
        array = FreshDiskArray('disk')
        disk = AsyncDisk(mach, array)
#        disk = SyncDisk(mach, array)
        return DFS(disk)

    def pre_post(self, spec, impl, **kwargs):       
        name = FreshBitVec('name.pre', 64)
        parent = BitVecVal(1, 64)
       
        sb = impl._disk.read(0)
        imap = impl._disk.read(sb[2])
        off = FreshBitVec("off", 9)

        # new
        ino = FreshBitVec('ino.pre', 64)
        # TODO: remove this later if not being used:
        blkoff = FreshBitVec("boff.pre", BlockOffsetSort.size())
    
        
        pre = ForAll([name], Implies(name != 0, And(
            Implies(0 < spec._dirfn(parent, name),
                    parent == spec._parentfn(spec._dirfn(parent, name))),

            Implies(0 < impl.lookup(parent, name),
                    And(impl.lookup(parent, name) < sb[1],
                        spec.get_attr(spec.lookup(parent, name)) == impl.get_attr(impl.lookup(parent, name)))),

            spec.lookup(parent, name) == impl.lookup(parent, name),

        )))

        # verifying reads
#        pre = And(pre, 
#            ForAll(ino,
#                   Implies(0 < ino,
#                      spec.read(ino) == impl.read(ino))))
        
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
        
        # uncomment the second one to verify writes
        (spec, impl, (_, name0, _, _), (sino, iino)) = yield pre    # need more than 2 values to unpack
#        (spec, impl, (_, name0, _, _), (_, _), (sino, iino)) = yield pre    # (dani) TODO VERY CONFUSED HERE; SEE NOTES

# ((spec, impl, (_, name0, _, _),  (sino, iino)), (spec, simpl, (_, _), _)) = yield pre   # too many values to unpack
#        (spec, impl, _, (_, name0, _, _, _, _),  (sino, iino, _)) = yield pre #need more than 4 values to unpack
#        (spec, impl, (_, name0, _, _, _, _),  (sino, iino, _, _)) = yield pre # need more than 2 values to unpack
#        (spec, impl, (_, name0, _, _, _, _),  (sino, iino)) = yield pre # need more than 2 values to unpack
#        (spec, impl, (_, name0, _, _),  (sino, iino)) = yield pre # need more than 2 values to unpack
        # (spec, impl, (_, name0, _, _), (_, _), (sino, iino)) = yield pre    # need more than 4 values to unpack (*same version as with the comment above..*)
#        (spec, impl, (_, _), _)= yield pre   


        #print(self.show(pre))
        self.show(pre)
        
        if iino < 0:
            iino = impl.lookup(parent, name0)

        if self._solve(sino == iino):
            assertion(sino == iino)

        sb = impl._disk.read(0)
        imap = impl._disk.read(sb[2])

        # remove later
       # blkoff1 = BitVecVal(1, BlockOffsetSort.size())

        post = ForAll([name], Implies(name != 0, And(
            Implies(0 < spec._dirfn(parent, name),
                    parent == spec._parentfn(spec._dirfn(parent, name))),

            Implies(0 < impl.lookup(parent, name),
                    And(impl.lookup(parent, name) < sb[1],
                        spec.get_attr(spec.lookup(parent, name)) == impl.get_attr(impl.lookup(parent, name)))),

            spec.lookup(parent, name) == impl.lookup(parent, name),

        )))

        # verifying reads
#        post = And(post, 
#            ForAll(ino,
#                   Implies(0 < ino,
#                      spec.read(ino) == impl.read(ino))))

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
        print("MATCHING MKNOD")
        
        parent = BitVecVal(1, 64)
        name = FreshBitVec('name', 64)
        mode = FreshBitVec('mode', 64)
        mtime = FreshBitVec('mtime', 64)
        assertion(name != 0)
        yield (parent, name, mode, mtime)

#    def match_write(self):
#        print("MATCHING WRITE")
#        ino = FreshBitVec('match-write-ino', 64)
#        data = FreshBlock('match-write-data')
#        yield (ino, data)
##        ino = FreshBitVec('match-write-ino', 64)
##       data = FreshBlock('match-write-data')
##        ino = BitVecVal(10, 64)
##        data = ConstBlock(0)



if __name__ == '__main__':
    test.main()

# SKETCHES

# print in 
#        print('IMPL READ!!!', impl.read(impl.lookup(parent, name), BitVecVal(1, BlockOffsetSort.size())))
#        rd = impl.read(impl.lookup(parent, name), BitVecVal(1, BlockOffsetSort.size()))
#        print("TYPE IS", dir(rd))
     #  for r in rd:
            #print("r is", r)
      #      print("t rype is", r)

