"Sparse Matrix Support"

from info import __doc__

from base import *
from csr import *
from csc import *
from lil import *
from dok import *
from coo import *
from dia import *
from bsr import *
from csgraph import *

from construct import *
from extract import *

#from spfuncs import *

__all__ = filter(lambda s:not s.startswith('_'),dir())
from numpy.testing import Tester
test = Tester().test
bench = Tester().bench
