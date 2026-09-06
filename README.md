# Valorant Zoom Overlay

Lente de zoom externa para Valorant: una ventana tipo lupa dibujada sobre el centro de la pantalla que hace zoom en la mira **sin perder visión periférica**. Se activa/desactiva con una hotkey.

> **Aviso de seguridad:** herramienta 100% externa — **no** inyecta DLLs, **no** lee memoria del juego, **no** modifica archivos del juego ni automatiza entrada. Cada frame se renderiza la ventana en primer plano (el juego en Borderless) mediante `PrintWindow` a un DC en memoria, el rectángulo central se estira con `StretchBlt` sobre un bitmap y se presenta con `UpdateLayeredWindow` (técnica estándar de overlays transparentes). La lente nunca se oculta, así que no se captura a sí misma (sin retroalimentación) y no hay parpadeo. Usa la clase de ventana overlay que Vanguard tolera (precedente: Discord / Steam / OBS). Aun así, no hay garantía permanente: usa una cuenta de prueba y bajo tu propio riesgo. Requiere **Valorant en modo Borderless** (el fullscreen exclusivo oculta cualquier overlay).

## Requisitos

- Windows 10 u 11
- Python 3.x (sin dependencias de terceros, solo la librería estándar)

## Instalación

1. Descarga/copia la carpeta del proyecto a tu PC.
2. Asegúrate de tener Python 3 instalado (`python --version`).
3. (Opcional) Crea un acceso directo a `run.bat`.

## Cómo usar

1. Ejecuta `run.bat` o `python zoom_overlay.py`. Verás la confirmación de que la lente está lista.
2. Abre Valorant en **ajustes → Video → Modo de visualización: Borderless**.
3. Entra a The Range o a una partida personalizada.
4. Pulsa **Alt + X** para activar la lente sobre tu crosshair.
5. Pulsa **Alt + X** de nuevo para desactivarla.

> **Probarla sin Valorant (escritorio):** déjalo funcionando y pulsa **Alt + X** con una ventana maximizada enfocada (p. ej. el Explorador de archivos). La lente ampliará el contenido de esa ventana. Si el foco está en el escritorio, el programa te avisará en la consola.

## Controles

| Acción | Tecla |
| --- | --- |
| Activar / desactivar la lente | `Alt + X` |
| Subir zoom (x1.5 – x6) | `Alt + Flecha Arriba` |
| Bajar zoom | `Alt + Flecha Abajo` |
| Agrandar la lente | `Alt + Flecha Derecha` |
| Achicar la lente | `Alt + Flecha Izquierda` |

Los valores por defecto: tamaño de lente **320 px**, zoom **x2.5**.

## Configuración

Edita `config.py` y reinicia el programa:

| Variable | Descripción |
| --- | --- |
| `ZOOM` | Zoom inicial (1.5 – 6.0, paso `ZOOM_STEP=0.5`) |
| `LENS_SIZE` | Tamaño inicial de la lente en píxeles |
| `LENS_MIN` / `LENS_MAX` | Límites de tamaño al redimensionar |
| `LENS_ROUNDED` | `True` = lente circular, `False` = cuadrada |
| `REFRESH_MS` | Milisegundos entre refrescos de la lente (16 = ~60 FPS, 33 = ~30 FPS) |
| `HOTKEY_TOGGLE`, `HOTKEY_ZOOM_IN`, `HOTKEY_ZOOM_OUT`, `HOTKEY_SIZE_UP`, `HOTKEY_SIZE_DOWN` | Códigos de tecla de Virtual-Key |

## Depuración

Ejecuta `run.bat --debug` (o `python zoom_overlay.py --debug`) para imprimir
arquitectura de Python, el handle de la ventana y la configuración activa. Si
aparece algún fallo interno, se muestra en consola y se guarda en `error.log`
junto al script. Si la lente se ve "suave", sube `REFRESH_MS` a `33`.

## Consejos

- El crosshair del juego se ve agrandado dentro de la lente: puedes desactivar el crosshair in-game y usar la lente como punto de puntería, o reducir el zoom.
- Si la lente aparece en negro sobre el juego, cambia a modo Borderless (el fullscreen exclusivo no permite capturar).
- La lente amplía la ventana que esté enfocada: en juego es Valorant; en el escritorio, la ventana activa.
- La lente es opaca (los píxeles se presentan con opacidad 255) y las esquinas fuera del círculo las recorta la región de la ventana.
- Para cerrar: cierra la ventana de consola o pulsa `Ctrl + C`.

## Estructura

```
valorant_zoom/
├── zoom_overlay.py   Código principal (ventana lupa + captura PrintWindow)
├── config.py         Configuración editable
└── run.bat           Lanzador para Windows
```

## Descargo de responsabilidad

Proyecto educativo. El uso de herramientas de ayuda visual puede violar los Términos de Servicio de algunos juegos y cambiarlos en cualquier momento. Úsalo solo en cuentas de prueba y asume el riesgo.