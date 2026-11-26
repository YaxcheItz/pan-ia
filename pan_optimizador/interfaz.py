"""Servidor local y datos del panel de demostración."""

import hashlib
import json
import os
import subprocess
import sys
import time
import webbrowser
from dataclasses import asdict, replace
from fractions import Fraction
from http.client import HTTPConnection, HTTPException
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .genetico import Configuracion, optimizar
from .modelo import Escenario, leer_escenario, medir, validar_escenario

RAIZ = Path(__file__).resolve().parents[1]
PANEL = Path(__file__).with_name("panel")
CONFIGURACION = Configuracion()
PUERTO_PANEL = 8765
INACTIVIDAD_SEGUNDOS = 30 * 60
IDENTIDAD_PANEL = hashlib.sha256(str(RAIZ).encode("utf-8")).hexdigest().encode("ascii")
RECURSOS = {
    "/": ("index.html", "text/html"),
    "/panel.css": ("panel.css", "text/css"),
    "/panel.js": ("panel.js", "text/javascript"),
}


def leer_escenarios_panel() -> dict[str, Escenario]:
    datos = RAIZ / "datos"
    escenarios = {}
    for carpeta in (datos, datos / "casos_limite"):
        for archivo in sorted(carpeta.glob("*.json")):
            if archivo.is_file():
                escenarios[archivo.relative_to(datos).as_posix()] = leer_escenario(archivo)
    return escenarios


def _porcentaje(valor: Fraction | None) -> float | None:
    return round(valor * 10000) / 100 if valor is not None else None


def _configuracion_panel(configuracion: Configuracion) -> dict:
    return {**asdict(configuracion), "elitismo": configuracion.elitismo}


def _calcular_plan(escenarios: dict[str, Escenario], datos: object) -> dict:
    if not isinstance(datos, dict):
        raise ValueError("Envía los datos del plan en un objeto JSON.")
    identificador = datos.get("escenario")
    if not isinstance(identificador, str):
        raise ValueError("Selecciona un escenario de la lista.")
    escenario = escenarios.get(identificador)
    if escenario is None and identificador != "personalizado":
        raise ValueError("Selecciona un escenario de la lista.")
    productos = datos.get("productos")
    if "productos" not in datos and escenario is not None:
        productos = [asdict(producto) for producto in escenario.productos]
    jornada = validar_escenario({
        "escenario": escenario.nombre if escenario else "Simulación personalizada",
        "masa_disponible_g": datos.get(
            "masa_disponible_g", escenario.masa_disponible_g if escenario else None
        ),
        "productos": productos,
    })
    semilla = datos.get("semilla", 42)
    if type(semilla) is not int:
        raise ValueError("Escribe una semilla entera.")

    opciones = datos.get("configuracion", {})
    if not isinstance(opciones, dict) or opciones.keys() - asdict(CONFIGURACION).keys():
        raise ValueError("Usa los parámetros de búsqueda disponibles en el panel.")
    configuracion = replace(CONFIGURACION, **opciones)

    genetico = optimizar(jornada, semilla, configuracion)
    metricas = medir(jornada, genetico.plan)
    demanda_total = jornada.demanda_total
    original = escenario or jornada
    return {
        "nombre": jornada.nombre,
        "masa_disponible_g": jornada.masa_disponible_g,
        "masa_modificada": jornada.masa_disponible_g != original.masa_disponible_g,
        "productos_modificados": jornada.productos != original.productos,
        "demanda_total": demanda_total,
        "configuracion": _configuracion_panel(configuracion),
        "genetico": {
            "piezas_totales": metricas.piezas_totales,
            "masa_usada_g": metricas.masa_usada_g,
            "masa_sobrante_g": metricas.masa_sobrante_g,
            "cobertura_minima_pct": _porcentaje(metricas.cobertura_minima),
            "cobertura_total_pct": _porcentaje(metricas.cobertura_total),
            "trivial": genetico.trivial,
            "generaciones_ejecutadas": genetico.generaciones_ejecutadas,
            "historial": [
                {
                    "cobertura_minima_pct": _porcentaje(minima if demanda_total else None),
                    "piezas_totales": piezas,
                    "masa_usada_g": gramos,
                }
                for minima, piezas, gramos in genetico.historial
            ],
        },
        "productos": [
            {
                **asdict(producto),
                "genetico": piezas,
                "pendientes": producto.demanda - piezas,
                "masa_asignada_g": piezas * producto.gramos_por_pieza,
                "cobertura_pct": _porcentaje(producto.cobertura(piezas)),
            }
            for producto, piezas in zip(jornada.productos, genetico.plan.piezas)
        ],
    }


class _PeticionPanel(BaseHTTPRequestHandler):
    server: "ServidorPanel"

    def log_message(self, formato, *argumentos):
        pass

    def _enviar(self, contenido, tipo, estado=200):
        self.send_response(estado)
        self.send_header("Content-Type", f"{tipo}; charset=utf-8")
        self.send_header("Content-Length", str(len(contenido)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(contenido)

    def _json(self, datos, estado=200):
        self._enviar(json.dumps(datos, ensure_ascii=False).encode("utf-8"), "application/json", estado)

    def _archivo(self, archivo: Path, tipo: str):
        try:
            contenido = archivo.read_bytes()
        except OSError:
            self._json({"error": f"El archivo «{archivo.name}» no está disponible."}, 404)
            return
        self._enviar(contenido, tipo)

    def do_GET(self):
        ruta = urlsplit(self.path).path
        if ruta in RECURSOS:
            archivo, tipo = RECURSOS[ruta]
            self._archivo(PANEL / archivo, tipo)
        elif ruta == "/api/estado":
            self._enviar(IDENTIDAD_PANEL, "text/plain")
        elif ruta == "/api/escenarios":
            self._json([
                {"id": clave, **asdict(esc)}
                for clave, esc in self.server.escenarios.items()
            ])
        elif ruta == "/api/configuracion":
            self._json({
                "configuracion": _configuracion_panel(CONFIGURACION),
            })
        elif ruta == "/favicon.ico":
            self._enviar(b"", "image/x-icon", 204)
        else:
            self._json({"error": "La página solicitada no existe."}, 404)

    def do_POST(self):
        if urlsplit(self.path).path != "/api/plan":
            self._json({"error": "La página solicitada no existe."}, 404)
            return
        if self.headers.get_content_type() != "application/json":
            self._json({"error": "Envía los datos del plan en formato JSON."}, 415)
            return
        try:
            longitud = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            longitud = 0
        if not 0 < longitud <= 1_048_576:
            self._json({"error": "La solicitud debe contener hasta 1 MB de datos JSON."}, 400)
            return
        try:
            datos = json.loads(self.rfile.read(longitud))
        except (ValueError, RecursionError):
            self._json({"error": "El contenido de la solicitud debe ser JSON válido."}, 400)
            return
        try:
            plan = _calcular_plan(self.server.escenarios, datos)
        except ValueError as error:
            self._json({"error": str(error)}, 400)
            return
        self._json(plan)


class ServidorPanel(ThreadingHTTPServer):
    allow_reuse_address = os.name != "nt"

    def __init__(self, puerto: int = 0):
        self.escenarios = leer_escenarios_panel()
        self.ultima_peticion = time.monotonic()
        super().__init__(("127.0.0.1", puerto), _PeticionPanel)

    def process_request(self, request, client_address):
        self.ultima_peticion = time.monotonic()
        super().process_request(request, client_address)


def _panel_activo(puerto: int) -> bool:
    conexion = HTTPConnection("127.0.0.1", puerto, timeout=0.35)
    try:
        conexion.request("GET", "/api/estado")
        with conexion.getresponse() as respuesta:
            return (
                respuesta.status == 200
                and respuesta.read(len(IDENTIDAD_PANEL) + 1) == IDENTIDAD_PANEL
            )
    except (OSError, HTTPException):
        return False
    finally:
        conexion.close()


def _iniciar_en_segundo_plano(puerto: int) -> int:
    puerto = puerto or PUERTO_PANEL
    if _panel_activo(puerto):
        return puerto

    if os.name == "nt":
        opciones = {"creationflags": subprocess.CREATE_NO_WINDOW}
    else:
        opciones = {"start_new_session": True}
    proceso = subprocess.Popen(
        [sys.executable, "-m", "pan_optimizador", "interfaz", "--sin-abrir",
         "--servidor-local", "--puerto", str(puerto)],
        cwd=RAIZ,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        **opciones,
    )
    limite = time.monotonic() + 6
    while time.monotonic() < limite:
        if _panel_activo(puerto):
            return puerto
        if proceso.poll() is not None:
            break
        time.sleep(0.08)
    if proceso.poll() is None:
        proceso.terminate()
        proceso.wait(timeout=3)
    raise ValueError(
        f"El panel no pudo iniciarse en el puerto {puerto}. "
        f"Ejecuta «python -m pan_optimizador interfaz --puerto {puerto}» "
        "para ver el motivo, o elige otro puerto."
    )


def ejecutar_panel(
    puerto: int, *, abrir_navegador: bool = True, segundo_plano: bool = False,
    servidor_local: bool = False,
):
    if not 0 <= puerto <= 65535:
        raise ValueError("«--puerto» debe estar entre 0 y 65535.")
    if segundo_plano:
        puerto = _iniciar_en_segundo_plano(puerto)
        url = f"http://127.0.0.1:{puerto}/"
        print(f"Abre el panel en {url}", flush=True)
        if abrir_navegador:
            webbrowser.open(url)
        return

    with ServidorPanel(puerto) as servidor:
        if servidor_local:
            servidor.timeout = 1
            while time.monotonic() - servidor.ultima_peticion < INACTIVIDAD_SEGUNDOS:
                servidor.handle_request()
            return

        url = f"http://127.0.0.1:{servidor.server_port}/"
        print(f"Abre el panel en {url}", flush=True)
        print("Mantén esta ventana abierta. Pulsa Ctrl+C para cerrar el panel.", flush=True)
        if abrir_navegador:
            webbrowser.open(url)
        try:
            servidor.serve_forever()
        except KeyboardInterrupt:
            print("\nPanel cerrado.")
