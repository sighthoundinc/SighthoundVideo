#!/usr/bin/env python 
# ----------------------------------------------------------------------
#  Copyright (C) 2009 Vitamin D, Inc. All rights reserved.
#
#  The information and source code contained herein is the
#  exclusive property of Vitamin D, Inc. No part of this software
#  may be used, reproduced, stored or distributed in any form,
#  without explicit written authorization from Vitamin D, Inc.
# ----------------------------------------------------------------------

"""Encodes the public interface to vitaToolbox.

This serves a double-purpose:
1. As a target to obfuscate.
2. As a way to generate sacred names for the public interface.

IMPORTANT:
- To run this properly with the obfuscator, it should be moved one directory up.
"""

# Utils to help obfuscate...
from obfuscation.ObfuscationUtils import sacredNames


# Import our public modules...
# ...keep track of globals before and after so we know what was imported.
oldGlobals = set(globals())

from vitaToolbox.cache import CacheManager
from vitaToolbox.dictUtils import OrderedDict
from vitaToolbox.image import ImageConversion
from vitaToolbox.image import Pil
from vitaToolbox.listUtils import Unique
from vitaToolbox.math import AlphaBetaFilter
from vitaToolbox.math import LineSegment
from vitaToolbox.math import Statistics
from vitaToolbox.mvc import AbstractModel
from vitaToolbox.path import FileCreationTime
from vitaToolbox.path import GetDiskSpaceAvailable
from vitaToolbox.path import RecursiveListDir
from vitaToolbox.profiling import MarkTime
from vitaToolbox.video import FrameGetter
from vitaToolbox.video import SimpleFrameCache
from vitaToolbox.video import TruthUtils
from vitaToolbox.wx import BetterScrolledWindow
from vitaToolbox.wx import BindChildren
from vitaToolbox.wx import CommandProcessorWithExtras
from vitaToolbox.wx import CreateMenuFromData
from vitaToolbox.wx import DeferredStatusBar
from vitaToolbox.wx import DirExistsValidator
from vitaToolbox.wx import FileBrowseButtonFixed
from vitaToolbox.wx import FixedGenBitmapButton
from vitaToolbox.wx import HtmlMessageDialog
from vitaToolbox.wx import OverlapSizer
from vitaToolbox.wx import PilImageWindow
from vitaToolbox.wx import TextSizeUtils

addedGlobals = (set(globals()) - oldGlobals) - set(['oldGlobals'])


##############################################################################
def main():
    """Our main code."""
    sacred = set()
    
    # Add sacred things for all of the imported modules...
    for g in addedGlobals:
        sacred |= sacredNames(globals()[g])
    
    # Print out the sacred names, separated by space...
    print ' '.join(sorted(sacred))


##############################################################################
if __name__ == '__main__':
    main()
