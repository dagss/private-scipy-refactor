#!/usr/bin/env python

"""
Simple script to invoke Cython (and Tempita) on all .pyx (.pyx.in)
files; while waiting for a proper build system. Uses file hashes to
figure out if rebuild is needed (using dates seem to fail with
frequent change of git branch).

For now, this scripts should be run by developers when changing Cython
files only, and the resulting files checked in, so that end-users (and
Python-only developers) do not get the Cython/Tempita dependencies.
"""

import os
import hashlib
import cPickle
import hashlib
from subprocess import Popen, PIPE

HASH_FILE = 'cythonize.dat'

#
# Rules
#
def process_pyx(fromfile, tofile):
    if os.system('cython --fast-fail -o "%s" "%s"' % (tofile, fromfile)) != 0:
        raise Exception('Cython failed')

def process_tempita_pyx(fromfile, tofile):
    import tempita
    with file(fromfile) as f:
        tmpl = f.read()
    pyxcontent = tempita.sub(tmpl)
    assert fromfile.endswith('.pyx.in')
    pyxfile = fromfile[:-len('.pyx.in')] + '.pyx'
    with file(pyxfile, 'w') as f:
        f.write(pyxcontent)
    process_pyx(pyxfile, tofile)

rules = {
    # fromext : (toext, function)
    '.pyx' : ('.c', process_pyx),
    '.pyx.in' : ('.c', process_tempita_pyx)
    }
#
# Hash db
#
def load_hashes(filename):
    # Return { filename : (sha1 of input, sha1 of output) }
    if os.path.isfile(filename):
        with file(filename) as f:
            hashes = cPickle.load(f)
    else:
        hashes = {}
    return hashes

def save_hashes(hash_db, filename):
    with file(filename, 'w') as f:
        cPickle.dump(hash_db, f)

def sha1_of_file(filename):
    h = hashlib.sha1()
    with file(filename) as f:
        h.update(f.read())
    return h.hexdigest()    

#
# interface with git
#

def execproc(cmd):
    assert isinstance(cmd, (list, tuple))
    pp = Popen(cmd, stdout=PIPE, stderr=PIPE)
    result = pp.stdout.read().strip()
    err = pp.stderr.read()
    retcode = pp.wait()
    if retcode != 0:
        return None
    else:
        return result

def git_last_commit_to(filename):
    out = execproc(['git', 'log', '-1', '--format=format:%H', filename])
    if out == '':
        out = None
    return out

def git_is_dirty(filename):
    out = execproc(['git', 'status', '--porcelain', filename])
    assert out is not None
    return (out != '')

def git_is_child(parent_sha, child_sha):
    out = execproc(['git', 'rev-list', child_sha, '^%s^' % parent_sha])
    assert out is not None
    for line in out.split('\n'):
        if line == parent_sha:
            return True
    return False

#
# Main program
#

def get_hash(frompath, topath):
    from_hash = sha1_of_file(frompath)
    to_hash = sha1_of_file(topath) if os.path.exists(topath) else None
    return (from_hash, to_hash)

def process(path, fromfile, tofile, processor_function, hash_db):
    fullfrompath = os.path.join(path, fromfile)
    fulltopath = os.path.join(path, tofile)
    current_hash = get_hash(fullfrompath, fulltopath)
    if current_hash == hash_db.get(fullfrompath, None):
        print '%s has not changed' % fullfrompath
        return

    from_sha = git_last_commit_to(fullfrompath)
    to_sha = git_last_commit_to(fulltopath)
    if (from_sha is not None and to_sha is not None and
        not git_is_dirty(fullfrompath)):
        # Both source and target is under revision control;
        # check with revision control system whether we need to
        # update
        if git_is_child(from_sha, to_sha):
            hash_db[fullfrompath] = current_hash
            print '%s is up to date (according to git)' % fullfrompath
            return

    orig_cwd = os.getcwd()
    try:
        os.chdir(path)
        print 'Processing %s' % fullfrompath
        processor_function(fromfile, tofile)
    finally:
        os.chdir(orig_cwd)
    # changed target file, recompute hash
    current_hash = get_hash(fullfrompath, fulltopath)
    # store hash in db
    hash_db[fullfrompath] = current_hash

hash_db = load_hashes(HASH_FILE)

for cur_dir, dirs, files in os.walk('scipy'):
    for filename in files:
        for fromext, rule in rules.iteritems():
            if filename.endswith(fromext):
                toext, function = rule
                fromfile = filename
                tofile = filename[:-len(fromext)] + toext
                process(cur_dir, fromfile, tofile, function, hash_db)
                save_hashes(hash_db, HASH_FILE)
                
