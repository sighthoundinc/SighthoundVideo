#*****************************************************************************
#
# RequestsUtils.py
#
#
#
#*****************************************************************************
#
#
# Copyright 2013-2022 Arden.ai, Inc.
#
# Licensed under the GNU GPLv3 license found at
# https://www.gnu.org/licenses/gpl-3.0.txt
#
# Alternative licensing available from Arden.ai, Inc.
# by emailing opensource@ardenai.com
#
# This file is part of the Arden AI project which can be found at
# https://github.com/ardenaiinc/ArdenAI
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; using version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02111, USA.
#
#
#*****************************************************************************
import os
import sys


#===========================================================================
def cacertLocation():
    """ overrides certifi.core.where to return actual location of cacert.pem"""

    path1 = os.path.realpath(__file__)  # ./library.zip/vitaToolbox/networking/RequestsUtils.py
    path2 = os.path.dirname(path1)      # ./library.zip/vitaToolbox/networking
    path3 = os.path.dirname(path2)      # ./library.zip/vitaToolbox
    path4 = os.path.dirname(path3)      # ./library.zip
    path5 = os.path.dirname(path4)      # ./
    if sys.platform == "darwin":
        path5 = os.path.dirname(path5)  # out of MacOS
        path5 = os.path.join(path5, "Resources") # and into ./Resources
    return os.path.join(path5, "config", "cacert.pem")


#===========================================================================
# We need to overrride the default cacert.pem location in packaged environment
def fixupCacertLocation():
    if hasattr(sys, "frozen"):
        import certifi.core

        os.environ["REQUESTS_CA_BUNDLE"] = cacertLocation()
        certifi.core.where = cacertLocation

        # delay importing until after where() has been replaced
        import requests.utils
        import requests.adapters
        # replace these variables in case these modules were
        # imported before we replaced certifi.core.where
        requests.utils.DEFAULT_CA_BUNDLE_PATH = cacertLocation()
        requests.adapters.DEFAULT_CA_BUNDLE_PATH = cacertLocation()
