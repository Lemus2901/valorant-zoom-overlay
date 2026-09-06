"""Lente de zoom externa para Valorant (lupa sobre el centro de pantalla).

Uso (Windows, Python 3.x sin dependencias de terceros):
    python zoom_overlay.py [--debug]

Hotkeys por defecto (todas con Alt):
    Alt + X          activar / desactivar la lente
    Alt + Flecha Arriba    subir zoom
    Alt + Flecha Abajo     bajar zoom
    Alt + Flecha Derecha   agrandar lente
    Alt + Flecha Izquierda achicar lente

Seguridad (por que es externo y de riesgo bajo):
    - No inyecta DLLs, no lee memoria del juego, no modifica archivos del juego,
      no automatiza entrada.
    - Captura GDI pura (BitBlt/StretchBlt) del sector de pantalla debajo de la
      lente y lo estira sobre una ventana transparente al mouse: no usa la
      Magnification API ni ninguna clase de Windows, por lo que no hay nada que
      dependa del registro de clases del sistema.
    - Ventana WS_EX_TOPMOST | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE:
      no roba foco ni clics y pertenece a la clase de overlays que Vanguard tolera
      (mismo precedente que Discord / Steam / OBS).
    - Requiere Valorant en modo Borderless; el fullscreen exclusivo oculta
      cualquier overlay a nivel de sistema operativo.
"""

import ctypes
import ctypes.wintypes as wt
import sys

import config

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
try:
    shcore = ctypes.windll.shcore
except Exception:
    shcore = None

WS_POPUP = 0x80000000
WS_CLIPCHILDREN = 0x02000000

WS_EX_TOPMOST = 0x00000008
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000

SW_HIDE = 0
SW_SHOWNOACTIVATE = 4
HWND_TOPMOST = -1
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001

LWA_ALPHA = 0x00000002

WM_HOTKEY = 0x0312
WM_DESTROY = 0x0002
WM_TIMER = 0x0113

ID_TOGGLE = 1
ID_ZOOM_IN = 2
ID_ZOOM_OUT = 3
ID_SIZE_UP = 4
ID_SIZE_DOWN = 5
ID_TIMER_REFRESH = 100

SRCCOPY = 0x00CC0020
HALFTONE = 4
PS_SOLID = 0
NULL_BRUSH = 5

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)
HCURSOR = wt.HANDLE
HGDIOBJ = wt.HANDLE


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wt.UINT),
        ("style", wt.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wt.HINSTANCE),
        ("hIcon", wt.HICON),
        ("hCursor", HCURSOR),
        ("hbrBackground", wt.HBRUSH),
        ("lpszMenuName", wt.LPCWSTR),
        ("lpszClassName", wt.LPCWSTR),
        ("hIconSm", wt.HICON),
    ]


user32.GetSystemMetrics.restype = ctypes.c_int
user32.GetSystemMetrics.argtypes = [ctypes.c_int]

kernel32.GetModuleHandleW.restype = wt.HINSTANCE
kernel32.GetModuleHandleW.argtypes = [wt.LPCWSTR]

user32.RegisterClassExW.restype = wt.ATOM
user32.RegisterClassExW.argtypes = [ctypes.POINTER(WNDCLASSEXW)]

user32.CreateWindowExW.restype = wt.HWND
user32.CreateWindowExW.argtypes = [
    wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wt.HWND, wt.HMENU, wt.HINSTANCE, wt.LPVOID,
]

user32.SetLayeredWindowAttributes.restype = ctypes.c_bool
user32.SetLayeredWindowAttributes.argtypes = [wt.HWND, wt.DWORD, wt.BYTE, wt.DWORD]

user32.DefWindowProcW.restype = LRESULT
user32.DefWindowProcW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]

user32.SetTimer.restype = ctypes.c_void_p
user32.SetTimer.argtypes = [wt.HWND, ctypes.c_void_p, wt.UINT, ctypes.c_void_p]

user32.KillTimer.restype = ctypes.c_bool
user32.KillTimer.argtypes = [wt.HWND, ctypes.c_void_p]

user32.SetWindowPos.restype = ctypes.c_bool
user32.SetWindowPos.argtypes = [
    wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.UINT,
]

user32.ShowWindow.restype = ctypes.c_bool
user32.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]

user32.RegisterHotKey.restype = ctypes.c_bool
user32.RegisterHotKey.argtypes = [wt.HWND, ctypes.c_int, wt.UINT, wt.UINT]

user32.UnregisterHotKey.restype = ctypes.c_bool
user32.UnregisterHotKey.argtypes = [wt.HWND, ctypes.c_int]

user32.SetWindowRgn.restype = ctypes.c_int
user32.SetWindowRgn.argtypes = [wt.HWND, wt.HRGN, ctypes.c_bool]

user32.PostQuitMessage.argtypes = [ctypes.c_int]

user32.GetMessageW.restype = ctypes.c_int
user32.GetMessageW.argtypes = [ctypes.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT]

user32.TranslateMessage.restype = ctypes.c_bool
user32.TranslateMessage.argtypes = [ctypes.POINTER(wt.MSG)]

user32.DispatchMessageW.restype = LRESULT
user32.DispatchMessageW.argtypes = [ctypes.POINTER(wt.MSG)]

user32.GetDC.restype = wt.HDC
user32.GetDC.argtypes = [wt.HWND]

user32.ReleaseDC.restype = ctypes.c_int
user32.ReleaseDC.argtypes = [wt.HWND, wt.HDC]

gdi32.CreateEllipticRgn.restype = wt.HRGN
gdi32.CreateEllipticRgn.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]

gdi32.SetStretchBltMode.restype = ctypes.c_int
gdi32.SetStretchBltMode.argtypes = [wt.HDC, ctypes.c_int]

gdi32.StretchBlt.restype = ctypes.c_bool
gdi32.StretchBlt.argtypes = [
    wt.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wt.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.DWORD,
]

gdi32.CreatePen.restype = HGDIOBJ
gdi32.CreatePen.argtypes = [ctypes.c_int, ctypes.c_int, wt.DWORD]

gdi32.SelectObject.restype = HGDIOBJ
gdi32.SelectObject.argtypes = [wt.HDC, HGDIOBJ]

gdi32.DeleteObject.restype = ctypes.c_bool
gdi32.DeleteObject.argtypes = [HGDIOBJ]

gdi32.GetStockObject.restype = HGDIOBJ
gdi32.GetStockObject.argtypes = [ctypes.c_int]

gdi32.Ellipse.restype = ctypes.c_bool
gdi32.Ellipse.argtypes = [wt.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]


class ZoomApp:
    def __init__(self):
        self.host = None
        self.wnd_proc_ref = None
        self.enabled = False
        self.debug = False
        self.zoom = config.ZOOM
        self.size = config.LENS_SIZE

    @staticmethod
    def _err_detail(err):
        try:
            return repr(ctypes.WinError(err))
        except Exception:
            return f"codigo de error {err:#010x}"

    def _make_dpi_aware(self):
        if shcore is not None:
            try:
                shcore.SetProcessDpiAwareness(2)
                return
            except Exception:
                pass
        user32.SetProcessDPIAware()

    def _register_class(self):
        self.wnd_proc_ref = WNDPROC(self._on_message)
        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wc.lpfnWndProc = self.wnd_proc_ref
        wc.hInstance = kernel32.GetModuleHandleW(None)
        wc.lpszClassName = "ValorantZoomHost"
        if not user32.RegisterClassExW(ctypes.byref(wc)):
            err = ctypes.get_last_error()
            raise RuntimeError("RegisterClassExW de la ventana host fallo: " + self._err_detail(err))

    def _create_window(self):
        ex_style = WS_EX_TOPMOST | WS_EX_TRANSPARENT | WS_EX_LAYERED | WS_EX_NOACTIVATE
        self.host = user32.CreateWindowExW(
            ex_style,
            "ValorantZoomHost",
            "ValorantZoom",
            WS_POPUP | WS_CLIPCHILDREN,
            0, 0, self.size, self.size,
            None, None, kernel32.GetModuleHandleW(None), None,
        )
        if not self.host:
            err = ctypes.get_last_error()
            raise RuntimeError("No se pudo crear la ventana lente: " + self._err_detail(err))
        user32.SetLayeredWindowAttributes(self.host, 0, 255, LWA_ALPHA)

    def _register_hotkeys(self):
        mods = config.HOTKEY_MODS
        user32.RegisterHotKey(self.host, ID_TOGGLE, mods, config.HOTKEY_TOGGLE)
        user32.RegisterHotKey(self.host, ID_ZOOM_IN, mods, config.HOTKEY_ZOOM_IN)
        user32.RegisterHotKey(self.host, ID_ZOOM_OUT, mods, config.HOTKEY_ZOOM_OUT)
        user32.RegisterHotKey(self.host, ID_SIZE_UP, mods, config.HOTKEY_SIZE_UP)
        user32.RegisterHotKey(self.host, ID_SIZE_DOWN, mods, config.HOTKEY_SIZE_DOWN)

    def setup(self):
        self._make_dpi_aware()
        if self.debug:
            arch = "x64" if ctypes.sizeof(ctypes.c_void_p) * 8 == 64 else "x86"
            print(f"[debug] Python {arch} | exec: {sys.executable}")
        self._register_class()
        self._create_window()
        self._register_hotkeys()
        self._apply_region()
        user32.SetTimer(self.host, ID_TIMER_REFRESH, config.REFRESH_MS, None)
        if self.debug:
            print(f"[debug] host={self.host:#x} zoom={self.zoom} size={self.size}"
                  f" refresh={config.REFRESH_MS}ms")

    def screen_center(self):
        return user32.GetSystemMetrics(0) // 2, user32.GetSystemMetrics(1) // 2

    def _apply_region(self):
        if config.LENS_ROUNDED:
            rgn = gdi32.CreateEllipticRgn(0, 0, self.size, self.size)
            user32.SetWindowRgn(self.host, rgn, True)

    def layout(self):
        cx, cy = self.screen_center()
        half = self.size // 2
        user32.SetWindowPos(
            self.host, HWND_TOPMOST,
            cx - half, cy - half, self.size, self.size,
            SWP_NOACTIVATE | SWP_SHOWWINDOW,
        )

    def _draw_border(self, hdc):
        old_brush = gdi32.SelectObject(hdc, gdi32.GetStockObject(NULL_BRUSH))
        pen_b = gdi32.CreatePen(PS_SOLID, 3, 0x00000000)
        old_pen = gdi32.SelectObject(hdc, pen_b)
        gdi32.Ellipse(hdc, 0, 0, self.size, self.size)
        gdi32.SelectObject(hdc, old_pen)
        gdi32.DeleteObject(pen_b)
        pen_w = gdi32.CreatePen(PS_SOLID, 1, 0x00FFFFFF)
        gdi32.SelectObject(hdc, pen_w)
        gdi32.Ellipse(hdc, 3, 3, self.size - 3, self.size - 3)
        gdi32.SelectObject(hdc, old_pen)
        gdi32.DeleteObject(pen_w)
        gdi32.SelectObject(hdc, old_brush)

    def _draw_lens(self):
        if not self.enabled:
            return
        user32.ShowWindow(self.host, SW_HIDE)
        try:
            hdc_screen = user32.GetDC(None)
            hdc_host = user32.GetDC(self.host)
            if hdc_screen and hdc_host:
                gdi32.SetStretchBltMode(hdc_host, HALFTONE)
                cx, cy = self.screen_center()
                srcw = max(1, int(round(self.size / self.zoom)))
                gdi32.StretchBlt(
                    hdc_host, 0, 0, self.size, self.size,
                    hdc_screen, cx - srcw // 2, cy - srcw // 2, srcw, srcw,
                    SRCCOPY,
                )
                if config.LENS_ROUNDED:
                    self._draw_border(hdc_host)
            if hdc_screen:
                user32.ReleaseDC(None, hdc_screen)
            if hdc_host:
                user32.ReleaseDC(self.host, hdc_host)
        finally:
            user32.SetWindowPos(
                self.host, HWND_TOPMOST,
                0, 0, 0, 0,
                SWP_NOACTIVATE | SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW,
            )

    def _refresh(self):
        if self.enabled:
            self._draw_lens()

    def toggle(self):
        self.enabled = not self.enabled
        if self.enabled:
            self.layout()
            self._draw_lens()
            print("[+] Lente activada")
        else:
            user32.ShowWindow(self.host, SW_HIDE)
            print("[-] Lente desactivada")

    def resize(self, delta):
        nuevo = self.size + delta
        if config.LENS_MIN <= nuevo <= config.LENS_MAX:
            self.size = nuevo
            self._apply_region()
            if self.enabled:
                self.layout()
                self._draw_lens()

    def set_zoom(self, zoom):
        self.zoom = max(config.ZOOM_MIN, min(config.ZOOM_MAX, zoom))
        if self.enabled:
            self.layout()
            self._draw_lens()

    def _on_hotkey(self, hotkey_id):
        if hotkey_id == ID_TOGGLE:
            self.toggle()
        elif hotkey_id == ID_ZOOM_IN:
            self.set_zoom(self.zoom + config.ZOOM_STEP)
        elif hotkey_id == ID_ZOOM_OUT:
            self.set_zoom(self.zoom - config.ZOOM_STEP)
        elif hotkey_id == ID_SIZE_UP:
            self.resize(config.LENS_STEP)
        elif hotkey_id == ID_SIZE_DOWN:
            self.resize(-config.LENS_STEP)

    def _on_message(self, hwnd, msg, wparam, lparam):
        if msg == WM_HOTKEY:
            self._on_hotkey(wparam)
            return 0
        if msg == WM_TIMER and wparam == ID_TIMER_REFRESH:
            self._refresh()
            return 0
        if msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def cleanup(self):
        user32.KillTimer(self.host, ID_TIMER_REFRESH)
        user32.UnregisterHotKey(self.host, ID_TOGGLE)
        user32.UnregisterHotKey(self.host, ID_ZOOM_IN)
        user32.UnregisterHotKey(self.host, ID_ZOOM_OUT)
        user32.UnregisterHotKey(self.host, ID_SIZE_UP)
        user32.UnregisterHotKey(self.host, ID_SIZE_DOWN)
        if self.host:
            user32.DestroyWindow(self.host)


def main():
    app = ZoomApp()
    app.debug = "--debug" in sys.argv
    try:
        app.setup()
    except Exception as exc:
        print("[ERROR]", exc)
        sys.exit(1)

    print("Lente de zoom lista. Hotkeys con Alt:")
    print("  Alt+X          activar/desactivar")
    print("  Alt+Flechas    ajustar zoom y tamano de la lente")
    print("  Cierra la consola o Ctrl+C para salir.")

    msg = wt.MSG()
    try:
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
    except KeyboardInterrupt:
        pass
    finally:
        app.cleanup()


if __name__ == "__main__":
    main()