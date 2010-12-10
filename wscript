top = '.'
out = 'build'

def recurse(ctx):
    ctx.recurse('scipy')

options = configure = build = recurse
