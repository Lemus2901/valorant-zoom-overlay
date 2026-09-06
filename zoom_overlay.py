"""Lente de zoom externa para Valorant (ventana tipo lupa sobre el centro de pantalla).

Uso (Windows, Python 3.x sin dependencias de terceros):
    python zoom_overlay.py

Hotkeys por defecto (todas con Alt):
    Alt + X          activar / desactivar la lente
    Alt + Flecha Arriba    subir zoom
    Alt + Flecha Abajo     bajar zoom
    Alt + Flecha Derecha   agrandar lente
    Alt + Flecha Izquierda achicar lente

Seguridad (por que es externo y de riesgo bajo):
    - No inyecta DLLs, no lee memoria del juego, no modifica archivos del juego,
      no automatiza entrada.
    - Usa la Magnification API de Windows (composicion DWM), la misma tecnologia
      del Magnificador del sistema operativo.
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
magnification = ctypes.WinDLL("Magnification.dll", use_last_error=True)
try:
    shcore = ctypes.windll.shcore
except Exception:
    shcore = None

WS_POPUP = 0x80000000
WS_CHILD = 0x40000000
WS_VISIBLE = 0x10000000
WS_CLIPSIBLINGS = 0x04000000
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

GWLP_WNDPROC = -4

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

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)
HCURSOR = wt.HANDLE


class MAG_RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_float),
        ("top", ctypes.c_float),
        ("right", ctypes.c_float),
        ("bottom", ctypes.c_float),
    ]


class MAGTRANSFORM(ctypes.Structure):
    _fields_ = [
        ("m", (ctypes.c_float * 3) * 3),
    ]


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

user32.GetClassInfoW.restype = ctypes.c_bool
user32.GetClassInfoW.argtypes = [wt.HINSTANCE, wt.LPCWSTR, ctypes.POINTER(WNDCLASSEXW)]

user32.DefWindowProcW.restype = LRESULT
user32.DefWindowProcW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]

user32.SetTimer.restype = ctypes.c_void_p
user32.SetTimer.argtypes = [wt.HWND, ctypes.c_void_p, wt.UINT, ctypes.c_void_p]

user32.KillTimer.restype = ctypes.c_bool
user32.KillTimer.argtypes = [wt.HWND, ctypes.c_void_p]

user32.InvalidateRect.restype = ctypes.c_bool
user32.InvalidateRect.argtypes = [wt.HWND, ctypes.c_void_p, ctypes.c_bool]

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

gdi32.CreateEllipticRgn.restype = wt.HRGN
gdi32.CreateEllipticRgn.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]

magnification.MagInitialize.restype = ctypes.c_bool
magnification.MagInitialize.argtypes = []

magnification.MagUninitialize.restype = ctypes.c_bool
magnification.MagUninitialize.argtypes = []

magnification.MagSetWindowSource.restype = ctypes.c_bool
magnification.MagSetWindowSource.argtypes = [wt.HWND, MAG_RECT]

magnification.MagSetWindowTransform.restype = ctypes.c_bool
magnification.MagSetWindowTransform.argtypes = [wt.HWND, ctypes.POINTER(MAGTRANSFORM)]


class ZoomApp:
    def __init__(self):
        self.host = None
        self.mag_window = None
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

    def _class_exists(self, hinst):
        info = WNDCLASSEXW()
        info.cbSize = ctypes.sizeof(WNDCLASSEXW)
        return bool(user32.GetClassInfoW(hinst, "ScreenMagnifier", ctypes.byref(info)))

    def _ensure_magnifier_class(self):
        if self._class_exists(None):
            if self.debug:
                print("[debug] Clase ScreenMagnifier presente (sistema)")
            return
        hmod = kernel32.GetModuleHandleW("Magnification.dll")
        if hmod and self._class_exists(hmod):
            if self.debug:
                print("[debug] Clase ScreenMagnifier presente (registrada por Magnification.dll)")
            return
        if self.debug:
            print("[debug] Clase ScreenMagnifier NO registrada -> la registro manualmente")
        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wc.lpfnWndProc = ctypes.cast(user32.DefWindowProcW, WNDPROC)
        wc.hInstance = kernel32.GetModuleHandleW(None)
        wc.lpszClassName = "ScreenMagnifier"
        if not user32.RegisterClassExW(ctypes.byref(wc)):
            err = ctypes.get_last_error()
            if self.debug:
                print("[debug] Registro manual de ScreenMagnifier fallo:", self._err_detail(err))

    def _create_windows(self):
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
            raise RuntimeError("No se pudo crear la ventana host: " + self._err_detail(err))
        user32.SetLayeredWindowAttributes(self.host, 0, 255, LWA_ALPHA)
        self.mag_window = user32.CreateWindowExW(
            0,
            "ScreenMagnifier",
            None,
            WS_CHILD | WS_VISIBLE | WS_CLIPSIBLINGS | WS_CLIPCHILDREN,
            0, 0, self.size, self.size,
            self.host, None, kernel32.GetModuleHandleW(None), None,
        )
        if not self.mag_window:
            err = ctypes.get_last_error()
            raise RuntimeError("No se pudo crear la ventana magnifier: " + self._err_detail(err))

    def _register_hotkeys(self):
        mods = config.HOTKEY_MODS
        user32.RegisterHotKey(self.host, ID_TOGGLE, mods, config.HOTKEY_TOGGLE)
        user32.RegisterHotKey(self.host, ID_ZOOM_IN, mods, config.HOTKEY_ZOOM_IN)
        user32.RegisterHotKey(self.host, ID_ZOOM_OUT, mods, config.HOTKEY_ZOOM_OUT)
        user32.RegisterHotKey(self.host, ID_SIZE_UP, mods, config.HOTKEY_SIZE_UP)
        user32.RegisterHotKey(self.host, ID_SIZE_DOWN, mods, config.HOTKEY_SIZE_DOWN)

    def setup(self):
        self._make_dpi_aware()
        if not magnification.MagInitialize():
            raise RuntimeError("MagInitialize fallo: la API de magnificacion no se pudo inicializar")
        if self.debug:
            print("[debug] MagInitialize() OK")
            arch = "x64" if ctypes.sizeof(ctypes.c_void_p) * 8 == 64 else "x86"
            print(f"[debug] Python {arch} | exec: {sys.executable}")
        self._ensure_magnifier_class()
        self._register_class()
        self._create_windows()
        self._register_hotkeys()
        self._apply_region()
        user32.SetTimer(self.host, ID_TIMER_REFRESH, config.REFRESH_MS, None)
        if self.debug:
            print(f"[debug] host={self.host:#x} mag_window={self.mag_window:#x}"
                  f" zoom={self.zoom} size={self.size} refresh={config.REFRESH_MS}ms")

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
        source = MAG_RECT(
            cx - self.size / (2.0 * self.zoom),
            cy - self.size / (2.0 * self.zoom),
            cx + self.size / (2.0 * self.zoom),
            cy + self.size / (2.0 * self.zoom),
        )
        magnification.MagSetWindowSource(self.mag_window, source)
        transform = MAGTRANSFORM()
        transform.m[0][0] = self.zoom
        transform.m[1][1] = self.zoom
        transform.m[2][2] = 1.0
        magnification.MagSetWindowTransform(self.mag_window, ctypes.byref(transform))

    def _refresh(self):
        if not self.enabled:
            return
        self.layout()
        user32.InvalidateRect(self.mag_window, None, True)

    def toggle(self):
        self.enabled = not self.enabled
        if self.enabled:
            self.layout()
            self._apply_region()
            user32.ShowWindow(self.host, SW_SHOWNOACTIVATE)
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

    def set_zoom(self, zoom):
        self.zoom = max(config.ZOOM_MIN, min(config.ZOOM_MAX, zoom))
        if self.enabled:
            self.layout()

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
        magnification.MagUninitialize()


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