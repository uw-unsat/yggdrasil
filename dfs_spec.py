import errno
from disk import assertion, debug, Stat
from yggdrasil.diskspec import *

class DFSSpec():
    def __init__(self, mach, dirfn, parentfn, modefn, mtimefn, datafn):
        self._mach = mach
        self._dirfn = dirfn
        self._modefn = modefn
        self._mtimefn = mtimefn
        self._parentfn = parentfn
        self._datafn = datafn

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

        return ino

    # For now, ignore size
    def set_attr(self, ino, size, mode,  mtime):
        self._modefn = self._modefn.update(ino, mode, guard = on)
        self._mtimefin = self._mtimefn.update(ino, mtime, guard = on)
    

    def write(self, ino, datablk): 
        # assertion that data fits in a block?
#        on = self._mach.create_on([])
        if 0 < ino:
            self._datafn = self._datafn.update(ino, datablk) #, guard=on)
        else:
            return BitVecVal(-errno.ENOENT, 64)
    

    # NOTE: "If" cannot handle functions as arguments
    # def read(self, ino, off):
    def read(self, ino):
        #assertion(ULT(off, 512))
        #assertion(UGE(off, 0))
        if 0 < ino:
            r = self._datafn(ino)
            return r
#            return r[off]
#            return self._datafn(ino)[off]
        else:
    #        return BitVecVal(-errno.ENOENT, 64)
            return ConstBlock(0)

    def crash(self, mach):
        return self.__class__(mach, self._dirfn, self._parentfn, self._modefn, self._mtimefn, self._datafn)


    # In the implementation, attributes can be cached by clients. Now, this could lead to consistency errors! 
    # One option to prevent inconsitencies is to first access the "last modified time" from the disk, and
    # if this time matches the time of the attributes stored on cache, then we know those attributes are all valid


# SKETCHES (from test_inode.py and dirinode.py)

 #   def _read(self, block):
 #       return self._datafn(block)

 #   def read(self, ino, off):
 #       return If(self.is_mapped(ino, off),
 #               self._read(self._map(Concat(ino, off))), ConstBlock(0))

 #   def _write(self, block, value):
 #       self._datafn = self._datafn.update(block, value)

 #   def write(self, ino, off, value):
 #       if not self.is_mapped(ino, off):
 #           return
 #       self._write(self._map(Concat(ino, off)), value)

 #   def alloc(self):
 #       block = FreshSize('alloc')
 #       assertion(self.is_free(block))
 #       self._freemap = self._freemap.update(block, BoolVal(False))
 #       return block

 #   def free(self, block, guard=BoolVal(True)):
 #       self._freemap = self._freemap.update(block, BoolVal(True), guard=guard)

 #   def is_free(self, block):
 #       return self._freemap(block)

 #   def inrange(self, off):
 #       return And(ULE(self._start, off), ULE(off, self._end))

 #   #############

 #   def is_mapped(self, ino, off):
 #       vbn = Concat(ino, off)
 #       block = self._map(vbn)
 #       return And(self.inrange(off), Not(self.is_free(block)), self._revmap(block) == vbn)

 #   #############

 #   def bmap(self, ino, off):
 #       if Or(self.is_mapped(ino, off), Not(self.inrange(off))):
 #           return

 #       vbn = Concat(ino, off)

 #       block = self.alloc()

 #       self._map = self._map.update(vbn, block)
 #       self._revmap = self._revmap.update(block, vbn)

 #       self._datafn = self._datafn.update(block, ConstBlock(0))
 
