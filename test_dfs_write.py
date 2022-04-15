import errno
from dfs import DFS
from dfs_spec import DFSSpec
from disk import assertion, debug, Stat

from yggdrasil.diskspec import *
from yggdrasil import test
from kvimpl import KVImpl

InoSort = BitVecSort(64)
def FreshIno(name):
    return FreshBitVec(name, InoSort.size())

class DFSRefinement(test.RefinementTest):
    def create_spec(self, mach):
        dirfn = FreshUFunction('dirfn', SizeSort, SizeSort, SizeSort)
        parentfn =  FreshUFunction('parentfn', SizeSort, SizeSort)
        modefn =  FreshUFunction('modefn', SizeSort, SizeSort)
        mtimefn =  FreshUFunction('mtimefn', SizeSort, SizeSort)
        datafn = FreshDiskArray('datafn')
        emptyfn = FreshUFunction('emptyfn', SizeSort, BoolSort())
        return DFSSpec(mach, dirfn, parentfn, modefn, mtimefn, datafn, emptyfn)

    def create_impl(self, mach):
        array = FreshDiskArray('disk')
        disk = AsyncDisk(mach, array)
        return DFS(disk)

    def pre_post(self, spec, impl, **kwargs):       
        name = FreshBitVec('name.pre', 64)
        parent = BitVecVal(1, 64)
       
        sb = impl._disk.read(0)
        imap = impl._disk.read(sb[2])
        off = FreshBitVec("off", 9)
        
        ino = FreshBitVec('ino.pre', 64)
        blkoff = FreshBitVec("boff.pre", BlockOffsetSort.size())

        pre = ForAll([name], Implies(name != 0, And(
            Implies(0 < spec._dirfn(parent, name),
                    parent == spec._parentfn(spec._dirfn(parent, name))),

            Implies(0 < impl.lookup(parent, name),
                    And(impl.lookup(parent, name) < sb[1],
                        spec.get_attr(spec.lookup(parent, name)) == impl.get_attr(impl.lookup(parent, name)))),

            spec.lookup(parent, name) == impl.lookup(parent, name),
        )))

        
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
        
        (spec, impl, (ino1, data), (sino, iino)) = yield pre

        self.show(pre)

        sb = impl._disk.read(0)
        imap = impl._disk.read(sb[2])

        post = ForAll([name], Implies(name != 0, And(
            Implies(0 < spec._dirfn(parent, name),
                    parent == spec._parentfn(spec._dirfn(parent, name))),

            Implies(0 < impl.lookup(parent, name),
                    And(impl.lookup(parent, name) < sb[1],
                        spec.get_attr(spec.lookup(parent, name)) == impl.get_attr(impl.lookup(parent, name)))),

            spec.lookup(parent, name) == impl.lookup(parent, name),
         
            # uncomment to verify reads:
             #   ForAll([ino],      
             #      Implies(And(0 < ino, Not(impl.server.is_empty(ino))),
             #       impl.read(ino) == spec.read(ino)))
      
        )))

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


    def match_write(self):
        print("MATCHING WRITE")

        ino = FreshIno('match-write-ino')
        data = FreshBlock('match-write-data')
        assertion(ino > 0)
        yield(ino, data)


if __name__ == '__main__':
    test.main()

