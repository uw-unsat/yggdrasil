import errno
from disk import assertion, debug, Stat
from yggdrasil.diskspec import *

class DFSSpec():
    #def __init__(self, mach, dirfn, parentfn, modefn, mtimefn, datafn):
    def __init__(self, mach, dirfn, parentfn, modefn, mtimefn, datafn, emptyfn):
        self._mach = mach
        self._dirfn = dirfn
        self._modefn = modefn
        self._mtimefn = mtimefn
        self._parentfn = parentfn
        self._datafn = datafn
        self._emptyfn = emptyfn
        # TODO: MAYBE COUNT NUMBER OF CHILDREN; SO WE CAN LIMIT MKNOD LIKE WE LIMIT IT IN THE IMPL?

        self._emptyfn = self._emptyfn.update(BitVecVal(0, 64), BoolVal(True))
        self._emptyfn = self._emptyfn.update(BitVecVal(1, 64), BoolVal(True))
        self._emptyfn = self._emptyfn.update(BitVecVal(2, 64), BoolVal(True))

    # In the implementation, lookup results can be cached (this should not affect consistentcy since we do not delete files)
    def lookup(self, parent, name):
        ino = self._dirfn(parent, name)
        return If(0 < ino, ino, -errno.ENOENT)

    def get_attr(self, ino):
        return Stat(size=0,
                    mode=self._modefn(ino),
                    mtime=self._mtimefn(ino))

    def mknod(self, parent, name, mode, mtime):
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
        self._emptyfn = self._emptyfn.update(ino, BoolVal(True))

        return ino

    # For now, ignore size
    def set_attr(self, ino, size, mode,  mtime):
        self._modefn = self._modefn.update(ino, mode, guard = on)
        self._mtimefin = self._mtimefn.update(ino, mtime, guard = on)

    def is_empty(self, ino):
        return self._emptyfn(ino)

    # TODO: write and read
    def write(self, ino, datablk): 
        #data = Extract(511, 0, data)
        if 0 < ino:
            self._datafn = self._datafn.update(ino, datablk) #, guard=on)
            self._emptyfn = self._emptyfn.update(ino, BoolVal(False))
        #else:
        #    return BitVecVal(-errno.ENOENT, 64)


    # NOTE: "If" cannot handle functions as arguments
    # def read(self, ino, off):
    def read(self, ino):
        return If(self.is_empty(ino), ConstBlock(0), self._datafn(ino))
        #if 0 < ino:
        #    return If(self.is_empty(ino), ConstBlock(0), self._datafn(ino))
        #else:
        #    return ConstBlock(0)

    def crash(self, mach):
        #return self.__class__(mach, self._dirfn, self._parentfn, self._modefn, self._mtimefn, self._datafn)
        return self.__class__(mach, self._dirfn, self._parentfn, self._modefn, self._mtimefn, self._datafn, self._emptyfn)


    # In the implementation, attributes can be cached by clients. Now, this could lead to consistency errors! 
    # One option to prevent inconsitencies is to first access the "last modified time" from the disk, and
    # if this time matches the time of the attributes stored on cache, then we know those attributes are all valid

