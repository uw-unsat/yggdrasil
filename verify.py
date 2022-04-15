import subprocess
import sys
import time
import pdb

files = [
#    To verify Yxv6, uncomment the 6 lines below
#    ('test_waldisk.py ', 'WAL Layer'),
#    ('test_xv6inode.py', 'Inode layer'),
#    ('test_dirspec.py', 'Directory layer'),
#    ('test_bitmap.py', 'Bitmap disk refinement'),
#    ('test_inodepack.py', 'Inode disk refinement'),
#    ('test_partition.py', 'Multi disk partition refinement'),

#   To verify YminLFS, uncomment the line below
#    ("test_lfs_og.py", "Verifying log file system")

     ("test_dfs.py", "mknod operation"),
     ("test_dfs_write.py", "write operation")
]

n = time.time()

#pdb.set_trace()  # uncomment to debug
for i, pt in files:
    sys.stdout.write('Verifying %s.' % pt)
    sys.stdout.flush()
    outp = ""
    lastp = time.time()
    w = subprocess.Popen('python2 %s' % i, shell=True, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    np = 0
    pn = time.time()
    while True:
#        print("oi")
        out = w.stderr.read(1)
#        print(out)
#        print(w.returncode)
        outp += out
        if not out:
#            print("not out")
            t = time.time() - pn
            sys.stdout.write("%s%f seconds\n" % ('.' * (50 - np - len(pt) - len(str(int(t)))), t))
            w.wait()
            if w.returncode != 0:
                print
                print 'Failure.'
                print outp
                sys.exit(1)
            break
        if out == '.': 
#        if out == '.' or '=':
            if time.time() - lastp > 1:
                np += 1
                sys.stdout.write(out)
                sys.stdout.flush()
                lastp = time.time()


print
#print 'Success. Verified lfs in %fs' % (time.time() - n)
print 'Success. Verified dfs in %fs' % (time.time() - n)

