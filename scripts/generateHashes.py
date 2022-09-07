#! /usr/bin/env python

# ----------------------------------------------------------------------
#  Copyright (C) 2009 Vitamin D, Inc. All rights reserved.
#
#  The information and source code contained herein is the
#  exclusive property of Vitamin D, Inc. No part of this software
#  may be used, reproduced, stored or distributed in any form,
#  without explicit written authorization from Vitamin D, Inc.
# ----------------------------------------------------------------------

# Generates hashes for using with FrontEnd.mk

import hashlib
import sys

hashList = []
for i, netPath in enumerate(sys.argv[1:]):
    hashList.append('sha1=%s' % (hashlib.sha1(file(netPath, 'rb').read()).hexdigest()))

print '&'.join(hashList)