
def configuration(parent_package='',top_path=None):
    from scipy.distutils.misc_util import Configuration
    config = Configuration('scipy',parent_package,top_path)
    config.add_subpackage('sandbox')
    return config

if __name__ == '__main__':
    from scipy.distutils.core import setup
    setup(**configuration(top_path='').todict())
