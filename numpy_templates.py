import os
import sys

from numpy.distutils.conv_template \
    import \
        process_str as process_c_str
from numpy.distutils.from_template \
    import \
        process_str as process_f_str

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

@extension(".src")
def src_template_hook(self, node):
    base_ext = node.change_ext("").suffix()
    if base_ext in [".f", ".pyf"]:
        return f_src_template_task(self, node)
    elif base_ext in [".c"]:
        return c_src_template_task(self, node)
    else:
        raise ValueError("Unknown suffix %s" % (base_ext + ".src",))

def c_src_template_task(self, node):
    out = node.change_ext("")
    target = node.parent.declare(out.name)
    ensure_dir(target.name)
    task = Task("numpy_c_template", inputs=[node], outputs=[target])
    task.gen = self
    task.env_vars = []
    task.env = self.env

    def execute(t):
        cnt = t.inputs[0].read()
        print "C TEMPLATE: %s -> %s" % (t.inputs[0], t.outputs[0])
        t.outputs[0].write(process_c_str(cnt))

    task.func = execute
    return [task]

def f_src_template_task(self, node):
    out = node.change_ext("")
    target = node.parent.declare(out.name)
    ensure_dir(target.name)
    task = Task("numpy_f_template", inputs=[node], outputs=[target])
    task.gen = self
    task.env_vars = []
    task.env = self.env

    def execute(t):
        cnt = t.inputs[0].read()
        print "F TEMPLATE: %s -> %s" % (t.inputs[0], t.outputs[0])
        t.outputs[0].write(process_f_str(cnt))

    task.func = execute
    return [task]
