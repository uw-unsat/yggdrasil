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
        emptyfn = FreshUFunction('emptyfn', SizeSort, BoolSort())
        #return DFSSpec(mach, dirfn, parentfn, modefn, mtimefn, datafn)
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
        
        # new
        ino = FreshBitVec('ino.pre', 64)
        blkoff = FreshBitVec("boff.pre", BlockOffsetSort.size())
        blkoff1 = BitVecVal(1, BlockOffsetSort.size())    
        blkoff32 = BitVecVal(32, BlockOffsetSort.size())    
#        impl.read(parent)._print()
#        print(type(impl.read(parent)))

        pre = ForAll([name], Implies(name != 0, And(
            Implies(0 < spec._dirfn(parent, name),
                    parent == spec._parentfn(spec._dirfn(parent, name))),

            Implies(0 < impl.lookup(parent, name),
                    And(impl.lookup(parent, name) < sb[1],
                        spec.get_attr(spec.lookup(parent, name)) == impl.get_attr(impl.lookup(parent, name)))),

            spec.lookup(parent, name) == impl.lookup(parent, name),
            
            # omg this finally works!!            
            Implies(0 < impl.lookup(parent, name),
                    spec.read(spec.lookup(parent, name)) == impl.read(impl.lookup(parent, name))),

            # Alternative way to verify reads:
#            ForAll([blkoff],
#                   Implies(0 < impl.lookup(parent, name), 
#                      spec.read(spec.lookup(parent, name))[blkoff] ==
#                           impl.read(impl.lookup(parent, name))[blkoff]))
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
        
        # uncomment the second one to verify writes; uncomment third one to verify ONLY writes
        (spec, impl, (_, name0, _, _), (sino, iino)) = yield pre   
        #(spec, impl, (_, name0, _, _, _, _), (_, _), (sino, iino)) = yield pre   
        #(spec, impl, (_, _), (sino, iino)) = yield pre

        #print(self.show(pre))
        self.show(pre)


        if iino < 0:
            iino = impl.lookup(parent, name0)

        if self._solve(sino == iino):
            assertion(sino == iino)
 
        sb = impl._disk.read(0)
        imap = impl._disk.read(sb[2])

        post = ForAll([name], Implies(name != 0, And(
            Implies(0 < spec._dirfn(parent, name),
                    parent == spec._parentfn(spec._dirfn(parent, name))),

            Implies(0 < impl.lookup(parent, name),
                    And(impl.lookup(parent, name) < sb[1],
                        spec.get_attr(spec.lookup(parent, name)) == impl.get_attr(impl.lookup(parent, name)))),

            spec.lookup(parent, name) == impl.lookup(parent, name),
        
            Implies(0 < impl.lookup(parent, name),
                    spec.read(spec.lookup(parent, name)) == impl.read(impl.lookup(parent, name)))

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

    def match_mknod(self):
        print("MATCHING MKNOD")
        
        parent = BitVecVal(1, 64)
        name = FreshBitVec('name', 64)
        mode = FreshBitVec('mode', 64)
        mtime = FreshBitVec('mtime', 64)
        assertion(name != 0)
        yield (parent, name, mode, mtime)

  #  def match_write(self):
  #      print("MATCHING WRITE")

# #       ino = FreshBitVec('match-write-ino', 64)
# #      data = FreshBlock('match-write-data')
  #      ino = BitVecVal(10, 64)
  #      data = ConstBlock(0)
  #      yield(ino, data)


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

#        print("IMPL IINO READ", impl.read(iino))   
#        print("IMPL IINO READ TYPE", type(impl.read(iino)))
#        print("SPEC IINO  READ", spec.read(iino))   
#        print("SPEC IINO READ TYPE", type(spec.read(iino)))
#        print("IMPL PARENT READ", impl.read(parent))
#        print("IMPL PARENT READ TYPE", type(impl.read(parent)))
#        print("SPEC PARENT READ", impl.read(parent))
#        print("SPEC PARENT READ TYPE", type(impl.read(parent)))
            
            # this works too (for post), but is a smaller guarantee (I think)
#            Implies(0 < iino,
#                impl.read(iino) == spec.read(sino))
           

            # this works too (but only verifies parent)
           # Implies(0 < parent,
           #     impl.read(parent) == spec.read(parent))

           # Implies(
           #     0 < ino, # this fails
           #     impl.read(ino) == spec.read(ino))

        #  can't even verify read equality for root inode...
#        spec.read(parent) == impl.read(parent)
            #   impl.read(parent) == impl.read(parent), # this is giving errors again, even though earlier (see below) it wasn't. OK nevermind I fixed it :) I was forgetting to return r in s_read...
#        spec.read(parent) == spec.read(parent) # this works fine
            
#        spec.read(BitVecVal(32, 64)) == impl.read(BitVecVal(32, 64))
 #       spec.read(BitVecVal(32, 64)) == spec.read(BitVecVal(32, 64)),#this works
     #   impl.read(BitVecVal(32, 64)) == impl.read(BitVecVal(32, 64)) #okkk now this works! (once we stop assigning a content block each time we mknod)
        

        #    Implies(0 < impl.lookup(parent, name),
        #            spec.read(spec.lookup(parent, name)) == impl.read(impl.lookup(parent, name)))
        ## verifying reads
        #    Implies(0 < impl.lookup(parent, name),
        #        ForAll([blkoff],
        #            spec.read(spec.lookup(parent, name))[blkoff] ==
        #                impl.read(impl.lookup(parent, name))[blkoff]))

