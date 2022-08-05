#!/usr/bin/env python

#*****************************************************************************
#
# ImageConversion.py
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
# https://github.url/thing
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


"""Collection of image conversion functions."""

# Python imports...
import ctypes
from ctypes import c_ubyte, cast, POINTER


# Not sure why this isn't the default for this function...
ctypes.pythonapi.PyCObject_AsVoidPtr.argtypes = [ctypes.py_object]
ctypes.pythonapi.PyCObject_AsVoidPtr.restype = ctypes.c_void_p

# Common 3rd-party imports...

numpy = None   # Imported lazily to avoid overhead when not used...
cv2 = None     # Imported lazily to avoid overhead when not used...
Image = None   # Imported lazily to avoid overhead when not used...
wx = None      # Imported lazily to avoid overhead when not used...

def needNumpy():
    global numpy
    if numpy is None:
        import numpy
def needCv():
    global cv2
    if cv2 is None:
        import cv2

def needImage():
    global Image
    if Image is None:
        from PIL import Image
def needWx():
    global wx
    if wx is None:
        import wx

# Toolbox imports...

# Local imports...

# This is the PIL Imaging type.  Use like this:
#    ctypes.pythonapi.PyCObject_AsVoidPtr.argtypes = [ctypes.py_object]
#    ctypes.pythonapi.PyCObject_AsVoidPtr.restype = ctypes.c_void_p
#    imaging = ctypes.cast(ctypes.pythonapi.PyCObject_AsVoidPtr(img.getim()),
#                          ctypes.POINTER(Imaging)                           )
#
#    numBytes = (imaging.contents.linesize * imaging.contents.ysize)
#    arr = ctypes.cast(imaging.contents.block,
#                      ctypes.POINTER(ctypes.c_ubyte * numBytes)).contents
#
# This is based off knowledge gleaned from the Imaging.h that comes with PIL...
class Imaging(ctypes.Structure):
    _fields_ = [
        ("mode", ctypes.c_char * 5),
        ("type", ctypes.c_int),
        ("depth", ctypes.c_int),     # NOT USED!
        ("bands", ctypes.c_int),     # 1, 2, 3, or 4
        ("xsize", ctypes.c_int),
        ("ysize", ctypes.c_int),

        ("palette", ctypes.c_void_p),

        # These allow you to get access one line at a time; if pixelsize is 1,
        # then you can use image8; else image32.
        ("image8",  ctypes.POINTER(ctypes.POINTER(ctypes.c_ubyte))),
        ("image32", ctypes.POINTER(ctypes.POINTER(ctypes.c_uint32))),

        # This always allows access of the image one line at a time, I think.
        ("image", ctypes.POINTER(ctypes.POINTER(ctypes.c_ubyte))),

        # IF (and only if) the image is one block of data, you can access it
        # with this...
        ("block", ctypes.POINTER(ctypes.c_ubyte)),

        # Number of bytes per pixel...
        ("pixelsize", ctypes.c_int),

        # Number of bytes per line (said to be xsize * pixelsize)
        ("linesize", ctypes.c_int),
    ]

##############################################################################
def getPilImaging(pilImg):
    """Returns the "imaging" structure for the given PIL image.

    @param  pilImg   The PIL image.
    @return imaging  The internal PIL imaging structure.
    """
    imaging = ctypes.cast(ctypes.pythonapi.PyCObject_AsVoidPtr(pilImg.getim()),
                          ctypes.POINTER(Imaging)                              )
    return imaging



##############################################################################
def convertPilToNumpy(pilImage):
    """Convert PIL image to a Numpy array.

    NOTES:
    - Pixel values in numpyImg are scaled to lie in the range [0.0, 1.0].

    @param  pilImg    Image represented as a PIL Image.
    @return numpyImg  Image represented as one NumPy array (grayscale images)
                      or a 3-dimensional NumPy array, where numpyImg[0] is the
                      R channel, numpyImg[1] is the G, and [2] is the B.
    """
    needNumpy()

    # Make a "float32" to divide by; we'll use this to force the buffer
    # to float32...
    f255 = numpy.float32(255.0)

    if pilImage.mode == 'RGB':
        # Optimized RGB algorithm; still could be faster since tostring()
        # ends up making a copy (not sure how to avoid that)...

        # Shorthand...
        width, height = pilImage.size

        # Convert to numpy, then divide by 255.0, which will switch us to a
        # 0.0 to 1.0 range _and_ copy the data.
        # NOTE: I think this handles the stride automatically, unlike the
        # PIL one (?)
        a = numpy.fromstring(pilImage.tobytes(), "B") / f255

        # Separate channels; all of this happens without copying...
        numpyImg = numpy.rollaxis(a.reshape((height, width, 3)), 2)
    else:
        numpyImg = numpy.asarray(pilImage.split()[0], 'B') / f255

    return numpyImg


##############################################################################
def convertNumpyToPil(numpyImg):
    """Convert an image stored as a tuple of NumPy arrays to a PIL Image.

    @param  numpyImg  Source numpy array or tuple of arrays between 0=1.0
    @return pilImage  A PIL Image
    """
    needNumpy()
    needImage()

    size = len(numpyImg)
    if size == 3:
        r = Image.fromarray(numpy.uint8(numpyImg[0]*255), "L")
        g = Image.fromarray(numpy.uint8(numpyImg[1]*255), "L")
        b = Image.fromarray(numpy.uint8(numpyImg[2]*255), "L")
        pilImage = Image.merge("RGB", (r,g,b))
    else:
        numpyImg = numpy.uint8(numpyImg * 255)
        pilImage = Image.fromarray(numpyImg, "L")

    return pilImage


##############################################################################
def convertNumpyToPilNoNorm(numpyImg):
    """Convert an image stored as a tuple of NumPy arrays to a PIL Image.

    @param  numpyImg  Source numpy array or tuple of arrays between 0=1.0
    @return pilImage  A PIL Image
    """
    needNumpy()
    needImage()

    size = len(numpyImg.shape)
    if size == 3:
        r = Image.fromarray(numpy.uint8(numpyImg[:,:,0]), "L")
        g = Image.fromarray(numpy.uint8(numpyImg[:,:,1]), "L")
        b = Image.fromarray(numpy.uint8(numpyImg[:,:,2]), "L")
        pilImage = Image.merge("RGB", (r,g,b))
    else:
        numpyImg = numpy.uint8(numpyImg)
        pilImage = Image.fromarray(numpyImg, "L")

    return pilImage


##############################################################################
def convertWxBitmapToPil(bitmap):
    """Convert the passed wx.Bitmap into pil.Image.

    @param bitmap    The source wx Bitmap object.
    @return pilImage  The resulting PIL Image.
    """
    needImage()
    needWx()

    size = tuple(bitmap.GetSize())
    try:
        buf = size[0]*size[1]*3*"\x00"
        bitmap.CopyToBuffer(buf)
    except:
        del buf
        buf = bitmap.ConvertToImage().GetData()
    return Image.frombuffer("RGB", size, buf, "raw", "RGB", 0, 1)


##############################################################################
def convertPilToWxBitmap(pilImage):
    """Convert the passed pill image into a wx.Bitmap.

    @param  pilImage  The source PIL Image.
    @return bitmap    The wx Bitmap object.
    """
    needWx()

    # This is the fastest I could figure out how to make this without a whole
    # bunch more work.  NOTE that on Mac, it seemed like you _could_ make things
    # faster by updating an existing bitmap using CopyFromBuffer if you
    # used the mode wx.BitmapBufferFormat_RGB32.  ...but this requires
    # having PIL output the string in BGRX mode, which slows down PIL a whole
    # lot...
    if pilImage.mode not in ('RGB', 'RGBA'):
        pilImage = pilImage.convert('RGB')

    if pilImage.mode == 'RGB':
        return wx.Bitmap.FromBuffer(pilImage.size[0], pilImage.size[1], pilImage.tobytes('raw', 'RGB'))
    else:
        return wx.Bitmap.FromBufferRGBA(pilImage.size[0], pilImage.size[1], pilImage.tobytes('raw', 'RGBA'))


##############################################################################
def convertNumpyToWxBitmap(a):
    """Convert the passed in numpy array (or tuple of arrays) into a Bitmap.

    @param  numpyImg  Source numpy array or tuple of arrays between 0=1.0
    @return bitmap    A wx.Bitmap
    """
    pilImage = convertNumpyToPil(a)
    bitmap = convertPilToWxBitmap(pilImage)
    return bitmap


##############################################################################
def convertClipFrameToWxBitmap(frame):
    """Convert the passed in RGB ClipFrame into a Bitmap.

    @param  numpyImg  Source numpy array or tuple of arrays between 0=1.0
    @return bitmap    A wx.Bitmap
    """
    needWx()

    buffer_from_memory = ctypes.pythonapi.PyBuffer_FromMemory
    buffer_from_memory.restype = ctypes.py_object

    buffSize = frame.width*frame.height*3
    buff = buffer_from_memory(frame.buffer, buffSize)
    bitmap = wx.Bitmap.FromBuffer(frame.width, frame.height, buff)
    return bitmap


##############################################################################
def convertClipFrameToNumpy(frame):
    """Convert the passed in RGB ClipFrame to a NumPy array.

        NOTES:
        - Pixel values in numpyImg are scaled to lie in the range [0.0, 1.0].

        @param  frame  The RGB ClipFrame to convert.
        @return numpyImg  Image represented as one NumPy array (grayscale images)
        or a 3-dimensional NumPy array, where numpyImg[0] is the
        R channel, numpyImg[1] is the G, and [2] is the B.
        """
    needNumpy()

    buffer_from_memory = ctypes.pythonapi.PyBuffer_FromMemory
    buffer_from_memory.restype = ctypes.py_object

    buffSize = numpy.dtype(numpy.uint8).itemsize*frame.width*frame.height*3
    buff = buffer_from_memory(frame.buffer, buffSize)

    # Create a "pythonic" ndarray sublcass that allows us to add additional
    # parameters since numpy.ndarray does not.
    class pyNdarray(numpy.ndarray): pass

    numpyImg = pyNdarray((frame.height, frame.width, 3), numpy.uint8, buff)

    # Add a reference to the buffer pointer so it isn't freed immediately.
    # It will be freed when this ndarray leaves scope.
    numpyImg.__sighthoundBufferRef = frame.structPtr

    # Return it...
    return numpyImg


##############################################################################
def convertClipFrameToBuffer( frame ):
    """Convert the passed in RGB ClipFrame to a raw buffer.

        @param  frame  The RGB ClipFrame to convert.
        @return buffer PyBuffer_FromMemory
        """

    print( 'make buffer_from_memory' )
    buffer_from_memory          = ctypes.pythonapi.PyBuffer_FromMemory
    buffer_from_memory.restype  = ctypes.py_object
    print( 'use buffer_from_memory' )
    buff                        = buffer_from_memory( frame.buffer,
                                                      1 * frame.width * frame.height * 3 )
                                                      #numpy.dtype(numpy.uint8).itemsize*frame.width*frame.height*3)
    return buff

##############################################################################
def convertClipFrameToPIL( frame ):
    """Convert the passed in RGB ClipFrame to a raw buffer.

        @param  frame  The RGB ClipFrame to convert.
        @return buffer PyBuffer_FromMemory
        """
    needImage()

    buffer_from_memory          = ctypes.pythonapi.PyBuffer_FromMemory
    buffer_from_memory.restype  = ctypes.py_object
    buff                        = buffer_from_memory( frame.buffer,
                                                      1 * frame.width * frame.height * 3 )
    pilImage = Image.frombuffer('RGB', (frame.width, frame.height), buff, 'raw', 'RGB', 0, 1)

    return pilImage

##############################################################################
def convertProcFrameToPIL( frame ):
    """Convert the passed in RGB StreamFrame to a raw buffer.

        @param  frame  The RGB ClipFrame to convert.
        @return buffer PyBuffer_FromMemory
        """
    needImage()
    return convertClipFrameToPIL( frame )
