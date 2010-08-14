import os
import sys
import re
import shutil
import subprocess

from yaku.task_manager \
    import \
        extension, get_extension_hook
from yaku.task \
    import \
        Task
from yaku.compiled_fun \
    import \
        compile_fun
from yaku.utils \
    import \
        ensure_dir, find_program
import yaku.errors

# Those regex are copied from build_src in numpy.distutils.command
F2PY_MODNAME_MATCH = re.compile(r'\s*python\s*module\s*(?P<name>[\w_]+)',
                                re.I).match
F2PY_UMODNAME_MATCH = re.compile(r'\s*python\s*module\s*(?P<name>[\w_]*?'\
                                     '__user__[\w_]*)',re.I).match
# End of copy
F2PY_INCLUDE_MATCH = re.compile(r'\s*\<include_file=([\S]+)\>').match

CGEN_TEMPLATE   = '%smodule'
FOBJECT_FILE    = 'fortranobject.c'
FWRAP_TEMPLATE  = '%s-f2pywrappers.f'

def modulename(node):

    def _modulename_from_txt(source):
        name = None
        for line in source.splitlines():
            m = F2PY_MODNAME_MATCH(line)
            if m:
                if F2PY_UMODNAME_MATCH(line): # skip *__user__* names
                    continue
                name = m.group('name')
                break
        return name
    return _modulename_from_txt(node.read())

def includes(filename):
    def _includes_from_txt(source):
        includes = []
        for line in source.splitlines():
            m = F2PY_INCLUDE_MATCH(line)
            if m:
                includes.append(m.group(1))
        return includes

    fid = open(filename)
    try:
        return _includes_from_txt(fid.read())
    finally:
        fid.close()

@extension(".pyf")
def f2py_task(self, node):
    return f2py_hook(self, node)

def f2py_hook(self, node):
    fobject = self.bld.bld_root.declare("f2py/fortranobject.c")
    if node.suffix() == ".pyf":
        modname =  modulename(node)
        target = node.parent.declare(modname + "module.c")
        fwrap = node.parent.declare(FWRAP_TEMPLATE % modname)
        # HACK: we write an empty file to force the file to exist if
        # f2py does not generate it (automatically detecting cases
        # where f2py generates / does not generate is too complicated)
        fwrap.write("")

        ensure_dir(target.name)
        
        task = Task("f2py", inputs=[node],
                    outputs=[target, fwrap, fobject])
        task.env_vars = []
        task.env = self.env

        task.func = f2py_func
        task.gen = self
        compile_task = get_extension_hook(".c")
        fcompile_task = get_extension_hook(".f")
        ctask = compile_task(self, target)
        ctask += compile_task(self, fobject)
        ctask += fcompile_task(self, fwrap)
        return [task] + ctask
    else:
        modname = self.target.split(".")[-1]
        target = node.parent.declare(modname + "module.c")
        task = Task("f2py", inputs=[node],
                    outputs=[target, fobject])
        task.env_vars = []
        task.env = self.env

        task.func = f2py_func_from_fortran
        task.gen = self

        compile_task = get_extension_hook(".c")
        ctask = compile_task(self, target)
        ctask += compile_task(self, fobject)

        fcompile_task = get_extension_hook(".f")
        ftask = fcompile_task(self, node)
        return [task] + ctask + ftask

def f2py_func(task):
    build_dir = task.outputs[0].parent.abspath()
    cmd = [i.path_from(task.gen.bld.bld_root) for i in task.inputs] \
          + ["--build-dir", build_dir, "--quiet"]
    f2py_cmd = [sys.executable, '-c',
                "\"from numpy.f2py.f2py2e import run_main;run_main(%s)\"" % repr(cmd)]
    p = subprocess.Popen(" ".join(f2py_cmd), shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=task.env["BLDDIR"])
    #for line in p.stdout.readlines():
    #    print line.strip()
    p.wait()
    assert p.returncode == 0

def configure(ctx):
    import numpy.f2py

    f2py_dir = ctx.bld_root.declare("f2py")

    d = os.path.dirname(numpy.f2py.__file__)
    source = os.path.join(d, 'src', "fortranobject.c")
    target = os.path.join(f2py_dir.abspath(), "fortranobject.c")
    ensure_dir(target)
    shutil.copy(source, target)

    source = os.path.join(d, 'src', "fortranobject.h")
    target = os.path.join(f2py_dir.abspath(), "fortranobject.h")
    shutil.copy(source, target)

    ctx.env["PYEXT_CPPPATH"].append(f2py_dir.get_bld().abspath())
    #ctx.env["CPPPATH"].append(f2py_dir)
    #print "CONFIGURING...."
