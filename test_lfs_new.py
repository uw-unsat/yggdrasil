# An even simpler file system
# Specification

import pdb
import errno
from lfs import ES
from disk import assertion, debug, Stat

from yggdrasil.diskspec import *
from yggdrasil import test

InoSort = BitVecSort(32)
NameSort = SizeSort 

class ESSpec(object):
    def __init__(self, mach):
        # might have to change data types
            
       self._mach - mach
       self._childmap = FreshUFunction("childmap", InoSort, NameSort, InoSort)
       self._parentmap = FreshUFunction("parentmap", InoSort, InoSort)
       self._mode = FreshUFunction("mode", InoSort, NameSort)
       self._time = FreshUFunction("time", InoSort, NameSort)
        
       # self._mach = mach 
       # self._childmap = FreshUFunction("childmap", SizeSort, SizeSort, SizeSort)
       # self._parentmap = FreshUFunction("parentmap", SizeSort, SizeSort)
       # self._mode = FreshUFunction("mode", SizeSort, SizeSort)
       # self._time = FreshUFunction("time", SizeSort, SizeSort)
       # #   TODO : self._sizemap


    def invariant(self):
        ino, name = FreshIno("ino"), FreshName("name")
        return ForAll([ino, name], Implies(
            self._childmap(ino, name) > 0,
            self._parentmap(self._childmap(ino, name)) == ino))

    def lookup(self, parent, name):
        ino = self._childmap(parent, name)
        return IF(0 < ino, ino, -errno.ENOENT)

#    def update(self, parent_ino, child_name, child_ino):
#        self._childmap = self._childmap.update([parent_ino, child_name], child_ino)

    def mknod(self, parent, name): #, mtime, mode
        #if to_bool(self._childmap(parent, name) > 0):
        if self.lookup(parent, name) > 0:
            return -errno.EEXIST

        # TODO: what is "on"?
        on = self._mach.create_on([])

        ino = FreshIno("ino")
        assertion(ino > 0)
        assertion(Not(self._parentmap(ino) > 0))

        # Update the directory structure.

        # QUESTION: WHY IS THIS NOT IN A TRANSACTION? (in the paper, it is)
        self._childmap = self._childmap.update((parent, name), ino, guard = on)
        self._parentmap = self._parentmap.update(ino, parent, guard = on)
        self._time = self._time.update(ino, time, guard = on)
        self._mode = self._mode.update(ino, mode, guard = on)

        return ino

    def get_attr(self, ino):
        return Stat(size = 0,
                    mode = self._mode(ino),
                    mtime = self._time(ino))

    # QUESTION: WHAT DOES THIS DO??
    def crash(self, mach):
        return self.__class__(mach, self._childmap, self._parentmap, self._mode, self._time)


    def equivalence(self, impl):
        ino, name = FreshIno("ino"), FreshName("name")
        return ForAll([ino, name], And(
            self.lookup(ino, name) == impl.lookup(ino, name),
            Implies(self.lookup(ino, name) > 0))) #,
               # self.stat(self.lookup(ino, name)) ==
               # impl.stat(impl.lookup(ino, name)))))


# TODO: see what is test.RefinementTest
class ESRefinement(test.RefinementTest):
    def create_spect(self, mach):
        return ESSPec(mach)

    def create_impl(self, mach):
        array = FreshDiskArray('disk')
        disk = AsyncDisk(mach, array)
        return ES(disk)

    def pre_post(self, spec, impl, **kwargs):
        #name = FreshName("name.pre")
        #parent = FreshIno("parent.pre")
        name = FreshBitVec('name.pre', 64)
        parent = BitVecVal(1, 64)

        superblock = impl._disk.read(0)
        imap = imp._disk.read(superblock[2])
        off = FreshBitVec('off', 9)
        #off = FreshName("off")
        
        # Parent and child mappings of valid (positive) inode numbers agree with each other
        pre = ForAll([name], Implies(name != 0, And(
                Implies(0 < spec._childmap(parent, name),
                    parent == spec._parentmap(spec._childmap(parent, name))),  

                Implies(0 < impl.lookup(parent, name),
                    And(impl.lookup(parent, name) < superblock[1],
                        spec.get_attr(spec.lookup(parent, name)) == impl.get_attr(impl.lookup(parent, name)))),
                    spec.lookup(parent, name) == impl.lookup(parent, name))))

        # ??
        pre = And(pre,
                ForAll([off],
                    Implies(
                        ZeroExt(64 - off.size(), off) < superblock[1],
                        And(imap[off] > 0, imap[off] < superblock[0]))))

        pre = And(pre,
                # Checking that allocated blocks are in range (0, allocator)
                0 < superblock[2],
                superblock[2] < superblock[0],
                0 < imap[1],
                imap[1] < superblock[0],

                # Root directory node has been allocated
                  1 < superblock[1], # QUESTION: HOW TO INTERPRET THE VALUES IN SUPERBLOCK??
                )

        # TODO: check out this "yield" function
        # ALSO, what do name0, sino, iino represent?
        (spec, impl, (_, name0, _, _), (sino, iino)) = yield pre

        self.show(pre)

        if iino < 0:
            iino = impl.lookup(parent, name0)

        if self._solve(sino == iino):
            assertion(sino == iino)

        # QUESTION: Interestingly, the verification fails if we do not redefine superblock here
        superblock = impl._disk.read(0)


        post = ForAll([name], Implies(name != 0, And(
                Implies(0 < spec._childmap(parent, name),
                    parent == spec._parentmap(spec._childmap(parent, name))),

                Implies(0 < impl.lookup(parent, name),
                    And(impl.lookup(parent, name) < superblock[1],
                        spec.get_attr(spec.lookup(parent, name)) == impl.get_attr(impl.lookup(parent, name)))),
                    spec.lookup(parent, name) == impl.lookup(parent, name))))

        post = And(post,
                ForAll([off],
                    Implies(
                        ZeroExt(64 - off.size(), off) < superblock[1],
                        And(imap[off] > 0, imap[off] < superblock[0]))))

        post = And(post,
                # Checking that allocated blocks are in range (0, allocator)
                0 < superblock[2],
                superblock[2] < superblock[0],
                0 < imap[1],
                imap[1] < superblock[0],

                # Root directory node has been allocated
                  1 < superblock[1], # QUESTION: HOW TO INTERPRET THE VALUES IN SUPERBLOCK??
                )
        yield post

    def match_mknod(self):
        parent = FreshIno("parent")
        name = FreshName("name")
        mode = FreshName("mode")
        time = FreshName("time")
        assertion(name != 0)
        yield (parent, name, mode, time)

