OS := $(shell uname)

PROFILE=False

CFLAGS=-DFUSE_USE_VERSION=26 `pkg-config --cflags python2` `pkg-config --cflags fuse`
LDFLAGS=`pkg-config --libs python2` `pkg-config --libs fuse`

ifeq ($(OS),Linux)
LDFLAGS += -shared
endif

ifeq ($(OS),Darwin)
LDFLAGS += -dynamiclib -Qunused-arguments
endif


all: diskimpl.so yav_dirimpl_fuse.so

prod: bitmap.so inodepack.so waldisk.so xv6inode.so yav_xv6_main.so dirinode.so

.PHONY: verify
verify: diskimpl.so
	python2 verify.py

%.so: %.o
	gcc -march=native -o $@ $< $(LDFLAGS)

%.o: %.c
	gcc -march=native -O2 -c -fPIC $(CFLAGS) $<

%.c: %.pyx
	cython -X profile=$(PROFILE) $<

%.c: %.py
	cythonize -X profile=$(PROFILE) $<

.SECONDARY:

.PHONY: clean
clean:
	rm -f *.so *.o *.c *.pyc
