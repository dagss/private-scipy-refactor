import os
import sys

def configuration(parent_package='',top_path=None):
    from scipy.distutils.misc_util import Configuration
    config = Configuration()
    config.add_subpackage('Lib')
    return config.todict()

if __name__ == '__main__':
    from scipy.distutils.core import setup
    setup(**configuration(top_path=''))
