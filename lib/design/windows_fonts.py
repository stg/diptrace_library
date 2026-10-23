"""Optional read-only Windows font measurements; no application or UI control.

Only temporary GDI font/device-context handles are created. The core document
reader has no dependency on this backend. DPI is an explicit export setting.
"""
import ctypes
from functools import lru_cache
import sys

from .vector_text import TextMetrics


class WindowsFontMetrics:
    def __init__(self, *, dpi=96):
        if sys.platform != 'win32':
            raise OSError('Windows font measurements require Windows')
        if not isinstance(dpi, int) or dpi <= 0:
            raise ValueError('font DPI must be a positive integer')
        from ctypes import wintypes as w
        self.dpi = dpi
        self.gdi = gdi = ctypes.WinDLL('gdi32', use_last_error=True)
        self.kernel = kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.Size = w.SIZE
        gdi.CreateCompatibleDC.argtypes, gdi.CreateCompatibleDC.restype = [w.HDC], w.HDC
        gdi.CreateFontW.argtypes = [ctypes.c_int]*5+[w.DWORD]*8+[w.LPCWSTR]
        gdi.CreateFontW.restype = w.HFONT
        gdi.SelectObject.argtypes, gdi.SelectObject.restype = [w.HDC, w.HGDIOBJ], w.HGDIOBJ
        gdi.DeleteObject.argtypes, gdi.DeleteObject.restype = [w.HGDIOBJ], w.BOOL
        gdi.DeleteDC.argtypes, gdi.DeleteDC.restype = [w.HDC], w.BOOL
        gdi.GetTextExtentPoint32W.argtypes = [w.HDC, w.LPCWSTR, ctypes.c_int, ctypes.POINTER(w.SIZE)]
        gdi.GetTextExtentPoint32W.restype = w.BOOL
        kernel.MulDiv.argtypes, kernel.MulDiv.restype = [ctypes.c_int]*3, ctypes.c_int

    @lru_cache(maxsize=4096)
    def measure(self, text, font_name, point_size):
        """Measure the whole UTF-16 string, including kerning and trailing spaces."""
        height = -self.kernel.MulDiv(point_size, self.dpi, 72)
        dc = self.gdi.CreateCompatibleDC(None)
        if not dc:
            raise ctypes.WinError(ctypes.get_last_error())
        font = old = None
        try:
            # Normal mapper selection also respects installed bitmap/system
            # faces; forcing TrueType can substitute a different requested face.
            font = self.gdi.CreateFontW(height, 0, 0, 0, 400, 0, 0, 0, 1, 0, 0, 0, 0, font_name)
            if not font:
                raise ctypes.WinError(ctypes.get_last_error())
            old = self.gdi.SelectObject(dc, font)
            if not old or old == ctypes.c_void_p(-1).value:
                raise ctypes.WinError(ctypes.get_last_error())
            size = self.Size()
            count = len(text.encode('utf-16-le', errors='surrogatepass'))//2
            if not self.gdi.GetTextExtentPoint32W(dc, text, count, ctypes.byref(size)):
                raise ctypes.WinError(ctypes.get_last_error())
            return TextMetrics(size.cx, size.cy)
        finally:
            if old and old != ctypes.c_void_p(-1).value:
                self.gdi.SelectObject(dc, old)
            if font:
                self.gdi.DeleteObject(font)
            self.gdi.DeleteDC(dc)
