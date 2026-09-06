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
    - Captura GDI pura: cada frame se copia la ventana en primer plano (el
      juego en modo Borderless) con BitBlt desde el DC de esa ventana (solo
      renderiza esa ventana, nunca los overlays que la tapan) y, si eso falla,
      con PrintWindow. El rectangulo central se estira con StretchBlt
      directamente sobre el DC de la lente. La lente es una ventana normal (sin
      estilos de capa) dibujada con GDI clasico, que siempre se muestra; los
      clics la atraviesan via WM_NCHITTEST=HTTRANSPARENT. Al no capturar la
      pantalla entera nunca se captura la lente a si misma (sin
      retroalimentacion) y no hay parpadeo. No usa la Magnification API ni el
      registro de clases de Windows.
    - Ventana WS_EX_TOPMOST | WS_EX_NOACTIVATE con region circular (esquinas
      invisibles): no roba foco ni clics y pertenece a la clase de overlays que
      Vanguard tolera (mismo precedente que Discord / Steam / OBS).
    - Requiere Valorant en modo Borderless; el fullscreen exclusivo oculta
      cualquier overlay a nivel de sistema operativo. Sin Valorant tambien
      funciona (amplia la ventana que este enfocada, p.ej. el Explorador).
"""

import ctypes
import ctypes.wintypes as wt
import os
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
WS_EX_NOACTIVATE = 0x08000000

SW_HIDE = 0
SW_SHOWNOACTIVATE = 4
HWND_TOPMOST = -1
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001

WM_HOTKEY = 0x0312
WM_DESTROY = 0x0002
WM_TIMER = 0x0113
WM_PAINT = 0x000F
WM_ERASEBKGND = 0x0014
WM_NCHITTEST = 0x0084

HTTRANSPARENT = -1

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
PW_RENDERFULLCONTENT = 0x00000002

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


class PAINTSTRUCT(ctypes.Structure):
    _fields_ = [
        ("hdc", wt.HDC),
        ("fErase", ctypes.c_int),
        ("rcPaint", wt.RECT),
        ("fRestore", ctypes.c_int),
        ("fIncUpdate", ctypes.c_int),
        ("rgbReserved", ctypes.c_ubyte * 32),
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

user32.GetForegroundWindow.restype = wt.HWND
user32.GetForegroundWindow.argtypes = []

user32.GetDesktopWindow.restype = wt.HWND
user32.GetDesktopWindow.argtypes = []

user32.GetClassNameW.restype = ctypes.c_int
user32.GetClassNameW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]

user32.GetClientRect.restype = ctypes.c_bool
user32.GetClientRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]

user32.ClientToScreen.restype = ctypes.c_bool
user32.ClientToScreen.argtypes = [wt.HWND, ctypes.POINTER(wt.POINT)]

user32.PrintWindow.restype = ctypes.c_bool
user32.PrintWindow.argtypes = [wt.HWND, wt.HDC, wt.UINT]

user32.BeginPaint.restype = wt.HDC
user32.BeginPaint.argtypes = [wt.HWND, ctypes.POINTER(PAINTSTRUCT)]

user32.EndPaint.restype = ctypes.c_int
user32.EndPaint.argtypes = [wt.HWND, ctypes.POINTER(PAINTSTRUCT)]

gdi32.CreateCompatibleDC.restype = wt.HDC
gdi32.CreateCompatibleDC.argtypes = [wt.HDC]

gdi32.CreateCompatibleBitmap.restype = HGDIOBJ
gdi32.CreateCompatibleBitmap.argtypes = [wt.HDC, ctypes.c_int, ctypes.c_int]

gdi32.BitBlt.restype = ctypes.c_bool
gdi32.BitBlt.argtypes = [
    wt.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wt.HDC, ctypes.c_int, ctypes.c_int, wt.DWORD,
]

gdi32.DeleteDC.restype = ctypes.c_bool
gdi32.DeleteDC.argtypes = [wt.HDC]

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
        self._tgt_w = 0
        self._tgt_h = 0
        self._tgt_dc = None
        self._tgt_bmp = None
        self._tgt_saved = None
        self._hinted_target = False
        self._warned_bitblt_black = False

    @staticmethod
    def _err_detail(err):
        try:
            return repr(ctypes.WinError(err))
        except Exception:
            return f"codigo de error {err:#010x}"

    @staticmethod
    def _log_error(exc):
        text = "[ERROR] " + repr(exc)
        print(text, file=sys.stderr, flush=True)
        try:
            path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "error.log")
            with open(path, "a", encoding="utf-8") as f:
                f.write(text + "\n")
        except Exception:
            pass

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
        ex_style = WS_EX_TOPMOST | WS_EX_NOACTIVATE
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

    def _register_hotkeys(self):
        mods = config.HOTKEY_MODS
        for ident, key in (
            (ID_TOGGLE, config.HOTKEY_TOGGLE),
            (ID_ZOOM_IN, config.HOTKEY_ZOOM_IN),
            (ID_ZOOM_OUT, config.HOTKEY_ZOOM_OUT),
            (ID_SIZE_UP, config.HOTKEY_SIZE_UP),
            (ID_SIZE_DOWN, config.HOTKEY_SIZE_DOWN),
        ):
            if not user32.RegisterHotKey(self.host, ident, mods, key):
                err = ctypes.get_last_error()
                if self.debug:
                    print(f"[debug] RegisterHotKey id={ident} fallo: {self._err_detail(err)}", flush=True)

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

    def _ensure_target_surface(self, w, h):
        if self._tgt_dc and self._tgt_w == w and self._tgt_h == h:
            return
        if self._tgt_dc:
            if self._tgt_saved:
                gdi32.SelectObject(self._tgt_dc, self._tgt_saved)
            if self._tgt_bmp:
                gdi32.DeleteObject(self._tgt_bmp)
            gdi32.DeleteDC(self._tgt_dc)
        self._tgt_dc = gdi32.CreateCompatibleDC(None)
        self._tgt_bmp = gdi32.CreateCompatibleBitmap(None, w, h)
        self._tgt_saved = gdi32.SelectObject(self._tgt_dc, self._tgt_bmp)
        self._tgt_w = w
        self._tgt_h = h

    def _paint_now(self):
        hdc = user32.GetDC(self.host)
        if not hdc:
            return
        try:
            self._compose(hdc)
        finally:
            user32.ReleaseDC(self.host, hdc)

    def _compose(self, hdc):
        hwnd = self._target_window()
        rect = wt.RECT()
        if not user32.GetClientRect(hwnd, ctypes.byref(rect)):
            return
        w, h = rect.right, rect.bottom
        if w <= 0 or h <= 0:
            return
        self._ensure_target_surface(w, h)
        if not self._capture_target(hwnd, w, h):
            if self.debug:
                print("[debug] Captura fallo (PrintWindow y BitBlt), frame anterior", flush=True)
            return
        gdi32.SetStretchBltMode(hdc, HALFTONE)
        pt = wt.POINT(0, 0)
        user32.ClientToScreen(hwnd, ctypes.byref(pt))
        cx, cy = self.screen_center()
        srcw = max(1, int(round(self.size / self.zoom)))
        srcx = (cx - pt.x) - srcw // 2
        srcy = (cy - pt.y) - srcw // 2
        if srcx < 0:
            srcx = 0
        if srcy < 0:
            srcy = 0
        if srcx + srcw > w:
            srcw = w - srcx
        if srcy + srcw > h:
            srcw = h - srcy
        if srcw > 0:
            gdi32.StretchBlt(
                hdc, 0, 0, self.size, self.size,
                self._tgt_dc, srcx, srcy, srcw, srcw,
                SRCCOPY,
            )
            if config.LENS_ROUNDED:
                self._draw_border(hdc)
        user32.SetWindowPos(
            self.host, HWND_TOPMOST,
            0, 0, 0, 0,
            SWP_NOACTIVATE | SWP_NOMOVE | SWP_NOSIZE,
        )

    def _target_window(self):
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            hwnd = user32.GetDesktopWindow()
        else:
            cls = ctypes.create_unicode_buffer(64)
            user32.GetClassNameW(hwnd, cls, len(cls))
            if cls.value in ("Progman", "WorkerW"):
                if not self._hinted_target:
                    print("[i] El foco esta en el escritorio. Para ver el zoom deja"
                          " otra ventana (p.ej. el Explorador max.) enfocada.", flush=True)
                    self._hinted_target = True
        return hwnd

    def _capture_target(self, hwnd, w, h):
        hdc_w = user32.GetDC(hwnd)
        ok = False
        if hdc_w:
            ok = gdi32.BitBlt(self._tgt_dc, 0, 0, w, h, hdc_w, 0, 0, SRCCOPY)
            user32.ReleaseDC(hwnd, hdc_w)
        if not ok:
            ok = user32.PrintWindow(hwnd, self._tgt_dc, PW_RENDERFULLCONTENT)
            if ok and not self._warned_bitblt_black and self.debug:
                print("[debug] BitBlt de la ventana no funciono; usando PrintWindow", flush=True)
                self._warned_bitblt_black = True
        return ok

    def _refresh(self):
        if self.enabled:
            self._paint_now()

    def toggle(self):
        self.enabled = not self.enabled
        if self.enabled:
            print("[+] Activando lente...", flush=True)
            self.layout()
            self._paint_now()
            print("[+] Lente activada", flush=True)
        else:
            user32.ShowWindow(self.host, SW_HIDE)
            print("[-] Lente desactivada", flush=True)

    def resize(self, delta):
        nuevo = self.size + delta
        if config.LENS_MIN <= nuevo <= config.LENS_MAX:
            self.size = nuevo
            self._apply_region()
            if self.enabled:
                self.layout()
                self._paint_now()

    def set_zoom(self, zoom):
        self.zoom = max(config.ZOOM_MIN, min(config.ZOOM_MAX, zoom))
        if self.enabled:
            self.layout()
            self._paint_now()

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
        try:
            if msg == WM_HOTKEY:
                self._on_hotkey(wparam)
                return 0
            if msg == WM_TIMER and wparam == ID_TIMER_REFRESH:
                self._refresh()
                return 0
            if msg == WM_PAINT:
                ps = PAINTSTRUCT()
                user32.BeginPaint(hwnd, ctypes.byref(ps))
                user32.EndPaint(hwnd, ctypes.byref(ps))
                return 0
            if msg == WM_ERASEBKGND:
                return 1
            if msg == WM_NCHITTEST:
                return HTTRANSPARENT
            if msg == WM_DESTROY:
                user32.PostQuitMessage(0)
                return 0
        except Exception as exc:
            self._log_error(exc)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def cleanup(self):
        user32.KillTimer(self.host, ID_TIMER_REFRESH)
        user32.UnregisterHotKey(self.host, ID_TOGGLE)
        user32.UnregisterHotKey(self.host, ID_ZOOM_IN)
        user32.UnregisterHotKey(self.host, ID_ZOOM_OUT)
        user32.UnregisterHotKey(self.host, ID_SIZE_UP)
        user32.UnregisterHotKey(self.host, ID_SIZE_DOWN)
        if self._tgt_dc:
            if self._tgt_saved:
                gdi32.SelectObject(self._tgt_dc, self._tgt_saved)
            if self._tgt_bmp:
                gdi32.DeleteObject(self._tgt_bmp)
            gdi32.DeleteDC(self._tgt_dc)
        if self.host:
            user32.DestroyWindow(self.host)


def main():
    print("Iniciando lente de zoom...", flush=True)
    app = ZoomApp()
    app.debug = "--debug" in sys.argv
    try:
        app.setup()
    except Exception as exc:
        print("[ERROR]", exc, flush=True)
        app._log_error(exc)
        sys.exit(1)

    print("Lente de zoom lista. Hotkeys con Alt:", flush=True)
    print("  Alt+X          activar/desactivar", flush=True)
    print("  Alt+Flechas    ajustar zoom y tamano de la lente", flush=True)
    print("  Cierra la consola o Ctrl+C para salir.", flush=True)

    msg = wt.MSG()
    try:
        while True:
            result = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if result == 0:
                break
            if result == -1:
                err = ctypes.get_last_error()
                print("[ERROR] GetMessage fallo: " + repr(ctypes.WinError(err)), flush=True)
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
    except KeyboardInterrupt:
        pass
    finally:
        app.cleanup()


if __name__ == "__main__":
    main()