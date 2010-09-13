import os
import sys
import copy
import re
import shutil
import subprocess

from yaku.task_manager \
    import \
        extension, get_extension_hook, set_extension_hook
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
    try:
        cnt = node.read()
        return _modulename_from_txt(cnt)
    except IOError:
        return os.path.splitext(node.name)[0]


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
def f2py_hook(self, node):
    return f2py_task(self, node)

def f2py_task(self, node):
    fobject = self.bld.bld_root.declare("f2py/fortranobject.c")
    if node.suffix() == ".pyf":
        modname = os.path.splitext(node.name)[0]
        target = node.parent.declare(modname + "module.c")
        fwrap = node.parent.declare(FWRAP_TEMPLATE % modname)
        # HACK: we write an empty file to force the file to exist if
        # f2py does not generate it (automatically detecting cases
        # where f2py generates / does not generate is too complicated)
        if not os.path.exists(fwrap.abspath()):
            fwrap.write("")

        ensure_dir(target.name)
        
        task = Task("f2py", inputs=[node],
                    outputs=[target, fwrap, fobject])
        task.env = self.env
        task.env_vars = ["F2PYFLAGS"]

        task.func = f2py_func
        task.gen = self
        return [task]
    else:
        raise ValueError(
                "Do not know how to handle extension %s in f2py tool")

def f2py_hook_fsources(self, modname, nodes):
    fobject = self.bld.bld_root.declare("f2py/fortranobject.c")

    for node in nodes:
        if not node.suffix() == ".f":
            raise ValueError("Wrong hook (expected only .f sources)")

    target = node.parent.declare(modname + "module.c")
    fwrap = node.parent.declare(FWRAP_TEMPLATE % modname)
    # HACK: we write an empty file to force the file to exist if
    # f2py does not generate it (automatically detecting cases
    # where f2py generates / does not generate is too complicated)
    if not os.path.exists(fwrap.abspath()):
        fwrap.write("")

    ensure_dir(target.name)
    
    task = Task("f2py", inputs=nodes, outputs=[target, fwrap, fobject])
    task.env = self.env
    task.env_vars = ["F2PYFLAGS"]

    task.func = lambda task: f2py_func(task, 
                                       ["--lower", "-m", modname])
    task.gen = self

    # We create tasks manually because list of .f -> extension does
    # not fit the yaku model of one file -> one task. Here, several
    # tasks share the same parameters (module names, etc..)
    compile_task = get_extension_hook(".c")
    fcompile_task = get_extension_hook(".f")
    ctasks = compile_task(self, target)
    ctasks += compile_task(self, fobject)
    ctasks += fcompile_task(self, fwrap)

    self.add_objects(ctasks)
    return [task] + ctasks

def f2py_func(task, extra_cmd=None):
    if extra_cmd is None:
        extra_cmd = []
    build_dir = task.outputs[0].parent.abspath()
    coutput = task.outputs[0].name
    f2py_wrapper = task.outputs[1].name
    cmd = [i.path_from(task.gen.bld.bld_root) for i in task.inputs] \
          + ["--build-dir", build_dir] + task.env["F2PYFLAGS"] \
          + ["--coutput", coutput, "--f2py-wrapper-output", f2py_wrapper] + \
          extra_cmd
    f2py_cmd = [sys.executable, '-c',
                "\"from numpy.f2py.f2py2e import run_main;" \
                "run_main(%s, True)\"" % repr(cmd)]
    if task.env["VERBOSE"]:
        print " ".join(f2py_cmd)
    else:
        print "F2PY         %s" % " ".join([str(i) for i in task.inputs])
    p = subprocess.Popen(" ".join(f2py_cmd), shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=task.env["BLDDIR"])
    for line in p.stdout.readlines():
        print line.strip()
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
    ctx.env["F2PYFLAGS"] = []

from yaku.tools.ctasks import _merge_env
class F2pyBuilder(object):
    def clone(self):
        return F2pyBuilder(self.ctx)

    def __init__(self, ctx):
        self.ctx = ctx
        self.env = copy.deepcopy(ctx.env)

        # FIXME: make tools modules available from yaku build context
        self.pyext = __import__("pyext")
        self.pyext_builder = ctx.builders["pyext"].clone()

    def extension_fsources(self, name, sources, env=None):
        env = _merge_env(self.env, env)
        return create_extension_fsources(self, name, sources, env)

def create_extension_fsources(f2py_builder, name, sources, env):
    """Python extension builder with fortran sources, with f2py hooked
    in the middle to build the f->c wrapper(s).
    
    You can use this directly as a callback when registering builder
    """
    bld = f2py_builder.ctx
    pyext = f2py_builder.pyext_builder
    pyext.env = env

    old_hook = get_extension_hook(".c")
    set_extension_hook(".c", f2py_builder.pyext.pycc_hook)
    try:
        sources = [bld.src_root.find_resource(s) \
                   for s in sources]
        fsources = [node for node in sources if node.suffix() == ".f"]
        modname = name.split(".")[-1]

        tasks = pyext.extension(name, sources)
        task_gen = tasks[0].gen

        f2py_tasks = f2py_hook_fsources(task_gen, modname, fsources)
        tasks += f2py_tasks
        bld.tasks += tasks
        return tasks
    finally:
        set_extension_hook(".c", old_hook)

def get_builder(ctx):
    return F2pyBuilder(ctx)
