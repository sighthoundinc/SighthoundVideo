#! /usr/local/bin/python

#*****************************************************************************
#
# GLCanvasSV.py
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

"""
## @file
Contains the classes leveraging OpenGL.
"""


# As stated from <http://www.py2exe.org/index.cgi/PyOpenGL>,
#   "As of PyOpenGL 3.0, add the following to any of your python files to
#   get py2exe to work."
# We need the couple of lines below for py2exe in Windows to make sure PyOpenGL
# gets packaged correctly.  We might be able to remove it once we switch over
# from py2exe to cx_Freeze...
import sys, ctypes
if sys.platform == 'win32':
    from ctypes import util
    try:
        from OpenGL.platform import win32
    except AttributeError:
        pass

from collections import defaultdict
from logging import getLogger
from appCommon.CommonStrings import kFrontEndLogName
from PIL import Image
import OpenGL.GL as gl
import wx
import traceback
from wx.glcanvas import GLCanvas
from wx.glcanvas import GLContext
from vitaToolbox.wx.OverlapSizer import OverlapSizer
from vitaToolbox.wx.BitmapWindow import BitmapWindow
from vitaToolbox.wx.BindChildren import bindChildren




def getGLAttribute(attr):
    try:
        res = gl.glGetString( attr )
        if res is None:
            res = '(none)'
    except:
        res = '(none)'
        getLogger(kFrontEndLogName).exception("Failed to retrieve " + str(attr))
    return res


_kDefaultInitSize = (640, 480)

# Different colors can be used for debugging purposes. For production, we use
# black as the preferred background color for OpenGL and Bitmap Video windows.
_kBlackColor = (0, 0, 0, 0)
_kWhiteColor = (255, 255, 255, 255)
# The color to use when clearing the background as a tuple (R, G, B, A) of
# integers with values [0, 255] with alpha, and three variants where postfix
# 'i' signifies a range of values in [0, 255], and 'f' signifies a range of
# values in [0.0, 1.0].
_kDefaultBgColorRGBAi = _kBlackColor
_kDefaultBgColorRGBi = _kDefaultBgColorRGBAi[0:3]
_kDefaultBgColorRGBAf = tuple([c/255.0 for c in _kDefaultBgColorRGBAi])
_kDefaultBgColorRGBf = _kDefaultBgColorRGBAf[0:3]


###########################################################
###########################################################
class GLExceptionSV( Exception ):
  def __init__(self, message, version):
        super(GLExceptionSV, self).__init__(message)
        self.version = "no OpenGL found" if version is None else version


###########################################################
###########################################################
class GLCanvasSV( GLCanvas ):
    kSizeMinX           = 4
    kSizeGranularityX   = 4
    kSizeOrPaintBitmapUpdateInterval    = 2

    ###########################################################
    def __init__( self, parent, location='(none)'):
        self._isInitialized = False
        dispAttrs = wx.glcanvas.GLAttributes()
        dispAttrs.PlatformDefaults().DoubleBuffer().EndList()
        GLCanvas.__init__(self, parent, id=wx.ID_ANY, dispAttrs=dispAttrs,)

        self.storedOffset       = ( 0, 0 )
        self.storedSize         = ( 1, 1 )
        self.bDidInitTexture    = False
        self._cacheFrameSizeWidth   = 0
        self._cacheFrameSizeHeight  = 0
        self._cacheSizeImage    = ( 0, 0 )
        self._cacheSizeWindow   = ( 0, 0 )
        self._texType = gl.GL_TEXTURE_2D
        self._internalFormat = gl.GL_RGB
        self._inputFormat = gl.GL_RGB

        self._cachedSetSize = None

        self._logger = getLogger(kFrontEndLogName)

        # from http://nullege.com/codes/show/src@g@l@glfwpy-HEAD@examples@04_textured_rectangle.py/211/OpenGL.GL.GL_VENDOR
        self.glContextSV = GLContextSV( self )
        self._glVendor              = getGLAttribute( gl.GL_VENDOR )
        self._glOpenGLVersion       = getGLAttribute( gl.GL_VERSION )
        self._glShadingLangVersion  = getGLAttribute( gl.GL_SHADING_LANGUAGE_VERSION )
        self._glRenderer            = getGLAttribute( gl.GL_RENDERER )
        self._glExtensions          = getGLAttribute( gl.GL_EXTENSIONS )

        self._location              = '(none)'
        if not location is None:
            self._location          = location

        self._logger.info('location=' + self._location + '  glVendor=\"' + self._glVendor + '\"  glOpenGLVersion=\"' + self._glOpenGLVersion +\
              '\"  glShadingLangVersion=\"' + self._glShadingLangVersion + '\"  glRenderer=\"' + self._glRenderer + '\"')
        version = self._glOpenGLVersion.split(".") if self._glOpenGLVersion is not None else None
        if version is None or len(version) < 1 or int(version[0]) < 2:
            raise GLExceptionSV("Incorrect GL version " + self._glOpenGLVersion + "!", self._glOpenGLVersion)
        # Extensions can be really long, like ...:
        #   GL_ARB_color_buffer_float GL_ARB_depth_buffer_float GL_ARB_depth_clamp GL_ARB_depth_texture GL_ARB_draw_buffers GL_ARB_draw_elements_base_vertex
        #       GL_ARB_draw_instanced GL_ARB_fragment_program GL_ARB_fragment_program_shadow GL_ARB_fragment_shader GL_ARB_framebuffer_object
        #       GL_ARB_framebuffer_sRGB GL_ARB_half_float_pixel GL_ARB_half_float_vertex GL_ARB_imaging GL_ARB_instanced_arrays GL_ARB_multisample
        #       GL_ARB_multitexture GL_ARB_occlusion_query GL_ARB_pixel_buffer_object GL_ARB_point_parameters GL_ARB_point_sprite GL_ARB_provoking_vertex
        #       GL_ARB_seamless_cube_map GL_ARB_shader_objects GL_ARB_shader_texture_lod GL_ARB_shading_language_100 GL_ARB_shadow GL_ARB_sync
        #       GL_ARB_texture_border_clamp GL_ARB_texture_compression GL_ARB_texture_compression_rgtc GL_ARB_texture_cube_map GL_ARB_texture_env_add
        #       GL_ARB_texture_env_combine GL_ARB_texture_env_crossbar GL_ARB_texture_env_dot3 GL_ARB_texture_float GL_ARB_texture_mirrored_repeat
        #       GL_ARB_texture_non_power_of_two GL_ARB_texture_rectangle GL_ARB_texture_rg GL_ARB_transpose_matrix GL_ARB_vertex_array_bgra
        #       GL_ARB_vertex_blend GL_ARB_vertex_buffer_object GL_ARB_vertex_program GL_ARB_vertex_shader GL_ARB_window_pos GL_EXT_abgr GL_EXT_bgra
        #       GL_EXT_bindable_uniform GL_EXT_blend_color GL_EXT_blend_equation_separate GL_EXT_blend_func_separate GL_EXT_blend_minmax
        #       GL_EXT_blend_subtract GL_EXT_clip_volume_hint GL_EXT_compiled_vertex_array GL_EXT_debug_label GL_EXT_debug_marker GL_EXT_depth_bounds_test
        #       GL_EXT_draw_buffers2 GL_EXT_draw_range_elements GL_EXT_fog_coord GL_EXT_framebuffer_blit GL_EXT_framebuffer_multisample
        #       GL_EXT_framebuffer_multisample_blit_scaled GL_EXT_framebuffer_object GL_EXT_framebuffer_sRGB GL_EXT_geometry_shader4
        #       GL_EXT_gpu_program_parameters GL_EXT_gpu_shader4 GL_EXT_multi_draw_arrays GL_EXT_packed_depth_stencil GL_EXT_packed_float
        #       GL_EXT_provoking_vertex GL_EXT_rescale_normal GL_EXT_secondary_color GL_EXT_separate_specular_color GL_EXT_shadow_funcs
        #       GL_EXT_stencil_two_side GL_EXT_stencil_wrap GL_EXT_texture_array GL_EXT_texture_compression_dxt1 GL_EXT_texture_compression_s3tc
        #       GL_EXT_texture_env_add GL_EXT_texture_filter_anisotropic GL_EXT_texture_integer GL_EXT_texture_lod_bias GL_EXT_texture_mirror_clamp
        #       GL_EXT_texture_rectangle GL_EXT_texture_shared_exponent GL_EXT_texture_sRGB GL_EXT_texture_sRGB_decode GL_EXT_timer_query
        #       GL_EXT_transform_feedback GL_EXT_vertex_array_bgra GL_APPLE_aux_depth_stencil GL_APPLE_client_storage GL_APPLE_element_array GL_APPLE_fence
        #       GL_APPLE_float_pixels GL_APPLE_flush_buffer_range GL_APPLE_flush_render GL_APPLE_object_purgeable GL_APPLE_packed_pixels
        #       GL_APPLE_pixel_buffer GL_APPLE_rgb_422 GL_APPLE_row_bytes GL_APPLE_specular_vector GL_APPLE_texture_range GL_APPLE_transform_hint
        #       GL_APPLE_vertex_array_object GL_APPLE_vertex_array_range GL_APPLE_vertex_point_size GL_APPLE_vertex_program_evaluators GL_APPLE_ycbcr_422
        #       GL_ATI_separate_stencil GL_ATI_texture_env_combine3 GL_ATI_texture_float GL_ATI_texture_mirror_once GL_IBM_rasterpos_clip GL_NV_blend_square
        #       GL_NV_conditional_render GL_NV_depth_clamp GL_NV_fog_distance GL_NV_fragment_program_option GL_NV_fragment_program2 GL_NV_light_max_exponent
        #       GL_NV_multisample_filter_hint GL_NV_point_sprite GL_NV_texgen_reflection GL_NV_texture_barrier GL_NV_vertex_program2_option
        #       GL_NV_vertex_program3 GL_SGIS_generate_mipmap GL_SGIS_texture_edge_clamp GL_SGIS_texture_lod
        # ... so not logging it:
        #   + '\"  glExtensions=\"' + self._glExtensions

        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)

        self._imgData = None
        self.InitTexture(True)

        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self._isInitialized = True


    ###########################################################
    def OnPaint(self, event):
        dc = wx.PaintDC(self)
        self.HandleDraw(True)

    ###########################################################
    def HandleDraw( self , doSwapBuffers=True):

        if not self._isInitialized:
            return

        # Don't waste precious CPU/GPU time drawing if we're hidden or not
        # shown on screen...
        if not self.IsShown():
            return

        # These functions can throw exceptions.  Let us catch them and print
        # them out in the logs, but don't let them leave this function so the
        # app can run undisturbed...
        try:
            gl.glClear( gl.GL_COLOR_BUFFER_BIT )

            # 2015-02-06  DLE  Without this, we get only 1 frame draw
            if self.bDidInitTexture:
                # enable textures, bind to our texture
                gl.glEnable( self._texType )
                gl.glBindTexture( self._texType, self.aGLTexture )

                gl.glViewport( self.storedOffset[0], self.storedOffset[1], self.storedSize[0], self.storedSize[1] )

                gl.glColor3f(*_kDefaultBgColorRGBf)
                # draw a quad
                gl.glBegin( gl.GL_QUADS )
                # transfer image to texture maintaining aspect ratio
                gl.glTexCoord2f( 0, 0 );    gl.glVertex2f( -1, 1.0 )
                gl.glTexCoord2f( 0, 1 );    gl.glVertex2f( -1, -1.0 )
                gl.glTexCoord2f( 1, 1 );    gl.glVertex2f( 1, -1.0 )
                gl.glTexCoord2f( 1, 0 );    gl.glVertex2f( 1, 1.0 )
                gl.glEnd()
                gl.glDisable( self._texType )
            if doSwapBuffers:
                self.SwapBuffers()
            else:
                gl.glFlush()
                gl.glFinish()
        except:
            self._logger.exception("")


    ###########################################################
    def OnSize( self, event ):
        sizeWindow  = self.GetClientSize()
        if self._cacheSizeImage == (0,0):
            self._cacheSizeImage = sizeWindow
        self.SetImageAndWindowSizes(self._cacheSizeImage, sizeWindow)
        if event is not None:
            event.Skip()
        self.Refresh()
        self.HandleDraw()


    ###########################################################
    def SetImageAndWindowSizes( self, sizeImage, sizeWindow, keepAspectRatio=True ):
        if not self.IsShown():
            self._cachedSetSize = (sizeImage, sizeWindow, keepAspectRatio)
            return

        self._cachedSetSize = None

        if self._cacheSizeImage == sizeImage and self._cacheSizeWindow == sizeWindow:
            self.SetCurrent( self.glContextSV )
            return

        offsetX = 0
        offsetY = 0
        imX     = sizeImage[ 0 ]
        imY     = sizeImage[ 1 ]
        windowX = sizeWindow[ 0 ]
        windowY = sizeWindow[ 1 ]
        if imY == 0 or windowY == 0:
            return

        ratioWindow = float( windowX ) / float( windowY )
        ratioImage  = float( imX ) / float( imY )
        widthAdj    = windowX
        heightAdj   = windowY
        if keepAspectRatio:
            if ratioWindow > ratioImage:
                widthAdj    = windowX * ratioImage / ratioWindow
                offsetX     = ( windowX - widthAdj ) / 2
            else:
                heightAdj   = windowY * ratioWindow / ratioImage
                offsetY     = ( windowY - heightAdj ) / 2
            if 0 != ( imX % 4 ):
                self._logger.error(
                    "UNEXPECTED ofx,ofy,imx,imy,winw,winh: " +
                    str(
                        (
                            int( offsetX ), int( offsetY ),
                            imX, imY, windowX, windowY
                        )
                    )
                )

        # 2015-01-16  DLE  Ha!  This SetCurrent to our GLContext is quite important.  It seems to update the size and
        # origin of the surface we paint within parent displayable.
        # 2015-01-22  DLE  ... and it seems important to SetCurrent immediately before the reshape (which used the global
        # gl) to avoid a multi-threaded / multi-canvas confusion about which is being rendered.  (In SV camera view, I
        # have multiple - at least the largeView and each small camera view.)
        self.SetCurrent( self.glContextSV )
        self.storedOffset = ( int( offsetX*self.GetContentScaleFactor() ), int( offsetY*self.GetContentScaleFactor() ) )
        self.storedSize = ( int( widthAdj*self.GetContentScaleFactor() ), int( heightAdj*self.GetContentScaleFactor() ))

        self._cacheSizeImage    = sizeImage
        self._cacheSizeWindow   = sizeWindow


    ###########################################################
    def InitTexture( self, setBitmap=False):
        if self.bDidInitTexture:
            return

        self.SetCurrent( self.glContextSV )

        gl.glClearColor(*_kDefaultBgColorRGBAf)

        # generate a texture id, make it current
        self.aGLTexture = gl.glGenTextures( 1 )
        gl.glBindTexture( self._texType, self.aGLTexture )

        # texture mode and parameters controlling wrapping and scaling
        gl.glTexEnvf( gl.GL_TEXTURE_ENV, gl.GL_TEXTURE_ENV_MODE, gl.GL_REPLACE )
        gl.glTexParameterf( self._texType, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP )
        gl.glTexParameterf( self._texType, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP )
        gl.glTexParameterf( self._texType, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR )
        gl.glTexParameterf( self._texType, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR )

        if setBitmap:
            pilImg = Image.new( 'RGB', _kDefaultInitSize )
            self.updateBitmap(pilImg)

        self.bDidInitTexture    = True

    ###########################################################
    def UpdateTextureRaw( self, data, width, height ):
        if not self.IsShown():
            return

        self.InitTexture()

        if self._cachedSetSize is not None:
            self.SetImageAndWindowSizes( self._cachedSetSize[0], self._cachedSetSize[1], self._cachedSetSize[2] )

        self.SetCurrent( self.glContextSV )
        if ( self._cacheFrameSizeWidth == width ) and ( self._cacheFrameSizeHeight == height ):
            # try the faster routine
            gl.glTexSubImage2D( self._texType, 0, 0, 0, width, height, self._inputFormat, gl.GL_UNSIGNED_BYTE, data )
        else:
            gl.glTexImage2D( self._texType, 0, self._internalFormat, width, height, 0, self._inputFormat, gl.GL_UNSIGNED_BYTE, data )
            self._cacheFrameSizeWidth   = width
            self._cacheFrameSizeHeight  = height

    ###########################################################
    def GetDesiredFrameSize( self ):
        winX, winY  = self.GetClientSize()
        desiredX    = winX - ( winX % GLCanvasSV.kSizeGranularityX )
        if desiredX < self.kSizeMinX:
            desiredX    = self.kSizeMinX
        sizeToReturn    = ( desiredX, winY )
        # if desiredX != winX:
        #    self._logger.info( 'adjusted sizeWindow vs sizeDesired: ' + str( self.GetClientSize() ) + '  ' + str( sizeToReturn ))

        return sizeToReturn

    ###########################################################
    def updateImageBuffer(self, data, width, height, keepAspectRatio=True ):
        try:
            sizeWindow  = self.GetClientSize()
            sizeFrame   = ( width, height )
            self.SetImageAndWindowSizes( sizeFrame, sizeWindow, keepAspectRatio )
            self._imgData = ( data, width, height )
            self.UpdateTextureRaw( data, width, height )
            self.HandleDraw(True)
        except:
            print("Crash in updateImageBuffer size %s" % traceback.format_exc())

    ###########################################################
    def GetImageData(self):
        return self._imgData

    ###########################################################
    def updateBitmap( self, bitmap ):
        # An incoming PIL Image tells us that our window has ended video updates and gone to an idle state.
        if bitmap is None:
            return

        width               = bitmap.size[0]
        height              = bitmap.size[1]
        asBuffer            = bitmap.tobytes('raw', 'RGB')
        if 0 != ( width % GLCanvasSV.kSizeGranularityX ):
            return
        self.updateImageBuffer( asBuffer, width, height )

    ###########################################################
    def updateImageData( self, frame ):
        self.updateImageBuffer( frame.buffer, frame.width, frame.height)


###########################################################
###########################################################
class GLContextSV( GLContext ):
    def __init__( self, winCanvas ):
        # Sometimes excepts like ...:
        # 2015-02-05 14:44:50,911 - WARNING - _core.py - ProcessEvent - GLContext.__init__( self, winCanvas )
        # 2015-02-05 14:44:50,911 - WARNING - _core.py - ProcessEvent -   File "/usr/local/lib/wxPython-3.0.1.1/lib/python2.7/site-packages/wx-3.0-osx_cocoa/wx/glcanvas.py", line 67, in __init__
        # 2015-02-05 14:44:50,911 - WARNING - _core.py - ProcessEvent - _glcanvas.GLContext_swiginit(self,_glcanvas.new_GLContext(*args, **kwargs))
        # 2015-02-05 14:44:50,911 - WARNING - _core.py - ProcessEvent - wx._core
        # 2015-02-05 14:44:50,912 - WARNING - _core.py - ProcessEvent - .
        # 2015-02-05 14:44:50,912 - WARNING - _core.py - ProcessEvent - PyAssertionError
        # 2015-02-05 14:44:50,912 - WARNING - _core.py - ProcessEvent - :
        # 2015-02-05 14:44:50,912 - WARNING - _core.py - ProcessEvent - C++ assertion "Assert failure" failed at /BUILD/wxPython-src-3.0.1.1/src/osx/cocoa/glcanvas.mm(42) in WXGLCreateContext(): NSOpenGLContext creation failed
        GLContext.__init__( self, winCanvas )
        self.SetCurrent( winCanvas )
        # Possibly this (fixed):
        #   http://trac.wxwidgets.org/ticket/16555#no1
        #try:
        #    GLContext.__init__( self, winCanvas )
        #    self.SetCurrent( winCanvas )
        #except Exception:
        #    pass



OsCompatibleGLCanvas = GLCanvasSV
GLCanvasControl = GLCanvasSV

