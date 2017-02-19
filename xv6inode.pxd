from diskimpl cimport *
from bitmap cimport BitmapDisk
from waldisk cimport WALDisk
from inodepack cimport InodePackDisk
from dirinode cimport DirImpl

cdef class InodeDisk:
    cdef public uint64_t _INODEDATADISK

    cdef readonly uint64_t _NDIRECT

    cdef WALDisk _txndisk
    cdef object _Bitmap
    cdef object _Allocator
    cdef object _Inode
    cdef Allocator _allocator
    cdef readonly BitmapDisk _bitmap
    cdef InodePackDisk _inode

    cdef void begin_tx(self)
    cdef void commit_tx(self)

    cdef Stat get_iattr(self, uint64_t ino)
    cdef void set_iattr(self, uint64_t ino, Stat attr)

    cdef Block read(self, uint64_t lbn)
    cdef void write_tx(self, uint64_t lbn, Block data)

    cdef uint64_t mappingi(self, uint64_t vbn)
    cdef bint is_mapped(self, uint64_t vbn)
    cdef bint is_free(self, uint64_t vbn)
    cdef uint64_t alloc(self)
    cdef void free(self, uint64_t lbn)
    cdef uint64_t bmap(self, uint64_t vbn)
    cdef void bunmap(self, uint64_t vbn)

cdef class IndirectInodeDisk:
    cdef readonly uint64_t _NINDIRECT

    cdef readonly InodeDisk _idisk

    cdef void begin_tx(self)
    cdef void commit_tx(self)

    cdef Stat get_iattr(self, uint64_t ino)
    cdef void set_iattr(self, uint64_t ino, Stat attr)

    cdef Block read(self, uint64_t lbn)
    cdef void write_tx(self, uint64_t lbn, Block data)

    cdef uint64_t mappingi(self, uint64_t vbn)
    cdef bint is_mapped(self, uint64_t vbn)
    cdef bint is_free(self, uint64_t vbn)
    cdef uint64_t bmap(self, uint64_t vbn)
    cdef void bunmap(self, uint64_t vbn)


cdef class FuseInode:
    cdef readonly uint64_t _NBLOCKS

    cdef readonly IndirectInodeDisk _idisk
    cdef WALDisk _txndisk
    cdef object _Allocator
    cdef Allocator _allocator
    cdef readonly BitmapDisk _bitmap

    cdef DentryLookup _dentryl

    cdef bint inode_is_free(self, uint64_t ino)
    cdef uint64_t ialloc(self)

    cdef Stat get_iattr(self, uint64_t ino)
    cdef void set_iattr(self, uint64_t ino, Stat attr)

    cdef tuple read(self, uint64_t ino, uint64_t off)
    cdef Block readb(self, uint64_t ino, uint64_t off)
    cdef uint64_t _write(self, uint64_t ino, uint64_t off, Block data, object osize=*)
    cdef uint64_t write(self, uint64_t ino, uint64_t off, Block data, object osize=*)

    cdef tuple _locate_dentry(self, uint64_t parent, uint64_t[15] name)
    cdef tuple _locate_empty_slot(self, uint64_t parent)
    cdef tuple _locate_nonempty_slot(self, uint64_t parent)

    cdef uint64_t _mknod(self, uint64_t parent, uint64_t[15] name, uint64_t mode)
    cdef uint64_t _rename(self, uint64_t oldparent, uint64_t[15] oldname, uint64_t newparent, uint64_t[15] newname)
    cdef uint64_t _unlink(self, uint64_t parent, uint64_t[15] name)
    cdef uint64_t _rmdir(self, uint64_t parent, uint64_t[15] name)

    cdef void bunmap(self, uint64_t ino, uint64_t off)

    cdef uint64_t mknod(self, uint64_t parent, uint64_t[15] name, uint64_t mode)
    cdef uint64_t rename(self, uint64_t oldparent, uint64_t[15] oldname, uint64_t newparent, uint64_t[15] newname)
    cdef uint64_t unlink(self, uint64_t parent, uint64_t[15] name)
    cdef uint64_t rmdir(self, uint64_t parent, uint64_t[15] name)
    cdef void flush(self)
    cdef uint64_t lookup(self, uint64_t parent, uint64_t[15] name)
