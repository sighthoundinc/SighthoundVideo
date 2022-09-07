#*****************************************************************************
#
# XmlUtils.py
#
#
#
#*****************************************************************************
#
#
# Copyright 2013-2022 Sighthound, Inc.
#
# Licensed under the GNU GPLv3 license found at
# https://www.gnu.org/licenses/gpl-3.0.txt
#
# Alternative licensing available from Sighthound, Inc.
# by emailing opensource@sighthound.com
#
# This file is part of the Sighthound Video project which can be found at
# https://github.com/sighthoundinc/SighthoundVideo
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

from xml.dom import minidom


###########################################################
def vitaParseXML(text):
    def strip_ns(elem):
        """ Strip namespaces from element names in XML structure
        """
        for el in elem:
            if '}' in el.tag:
                el.tag = el.tag.split('}', 1)[1]  # strip all namespaces
            strip_ns(el)

    md = None
    try:
        md = minidom.parseString(text)
    except ValueError, e:
        # minidom doesn't support multi-byte encodings ... reflow the document using UTF-8
        try:
            # sys.stderr.write("Got an exception! Rerunning the parser!")
            import xml.etree.ElementTree as ET
            xmlp = ET.XMLParser(encoding="utf-8")
            doc = ET.fromstringlist((text),parser=xmlp)
            strip_ns(doc)
            docAsStr = ET.tostring(doc, "utf-8", "xml")

            md = minidom.parseString(docAsStr)
        except:
            # re-raise the original exception
            raise e
    return md



