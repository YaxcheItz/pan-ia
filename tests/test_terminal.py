import csv
import json
import re
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from fractions import Fraction
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
ARCHIVOS = ("corridas.csv", "detalle_productos.csv", "evolucion.csv")


def invocar(*argumentos):
    return subprocess.run(
        [sys.executable, "-B", "-X", "utf8", "-m", "pan_optimizador", *map(str, argumentos)],
        cwd=RAIZ, capture_output=True, encoding="utf-8", timeout=30,
    )


def leer_csv(archivo):
    with archivo.open(encoding="utf-8", newline="") as entrada:
        return list(csv.DictReader(entrada))


def aptitud(fila):
    return Fraction(fila["aptitud_minima"]), int(fila["piezas_totales"]), int(fila["masa_usada_g"])


class TerminalTest(unittest.TestCase):
    def test_optimizar_muestra_tabla_totales_parametros_y_referencia(self):
        archivo = RAIZ / "datos" / "escasez_moderada.json"
        datos = json.loads(archivo.read_text(encoding="utf-8"))
        salida = invocar("optimizar", archivo, "--semilla", 42)
        self.assertEqual(salida.returncode, 0, salida.stderr)
        self.assertIn(datos["escenario"], salida.stdout)
        self.assertIn(f"Masa disponible  {datos['masa_disponible_g']} g", salida.stdout)
        self.assertIn("Semilla  42", salida.stdout)
        self.assertIn("Población 80 | Generaciones 160 | Torneo 3", salida.stdout)
        self.assertIn("Mejor plan encontrado", salida.stdout)
        for producto, piezas in zip(datos["productos"], (53, 31, 22)):
            with self.subTest(producto=producto["nombre"]):
                fila = next(linea for linea in salida.stdout.splitlines()
                            if linea.startswith(producto["nombre"]))
                nombre, demanda, producidas, pendientes, peso, asignada, cobertura = [
                    celda.strip() for celda in fila.split("|")
                ]
                self.assertEqual(nombre, producto["nombre"])
                self.assertEqual(int(demanda), producto["demanda"])
                self.assertEqual(int(producidas), piezas)
                self.assertEqual(int(pendientes), producto["demanda"] - piezas)
                self.assertEqual(int(peso), producto["gramos_por_pieza"])
                self.assertEqual(int(asignada), piezas * producto["gramos_por_pieza"])
                self.assertRegex(cobertura, r"^\d+,\d{2} %$")
        for texto in ("106 de 120", "9980 g", "20 g", "88,00 %", "88,33 %",
                      "El genético empata con el reparto proporcional"):
            self.assertIn(texto, salida.stdout)

    def test_comparar_regenera_csv_reconstruibles_y_cuenta_semillas_distintas(self):
        with tempfile.TemporaryDirectory() as carpeta:
            destino = Path(carpeta) / "csv"
            argumentos = (
                "comparar", "datos", "--semillas", 42, 7, 42, "--salida", destino,
                "--poblacion", 8, "--generaciones", 5, "--torneo", 2,
                "--prob-cruce", 1, "--prob-mutacion", 0.25,
            )
            salida = invocar(*argumentos)
            self.assertEqual(salida.returncode, 0, salida.stderr)
            corridas, detalle, evolucion = (leer_csv(destino / archivo) for archivo in ARCHIVOS)
            self.assertEqual([len(corridas), len(detalle), len(evolucion)], [12, 36, 38])
            escenarios = [archivo.name for archivo in sorted((RAIZ / "datos").glob("*.json"))]
            self.assertEqual(list(dict.fromkeys(fila["archivo"] for fila in corridas)), escenarios)
            resumenes = re.findall(r"Ganan (\d+) \| Empatan (\d+) \| Quedan por debajo (\d+)", salida.stdout)
            self.assertEqual(len(resumenes), 4)
            self.assertEqual(salida.stdout.count("Mejor aptitud"), 4)
            self.assertEqual(salida.stdout.count("Peor aptitud"), 4)

            for archivo, resumen in zip(escenarios, resumenes):
                with self.subTest(archivo=archivo):
                    filas = [fila for fila in corridas if fila["archivo"] == archivo]
                    referencia, *geneticos = filas
                    self.assertEqual(referencia["metodo"], "proporcional")
                    self.assertEqual(referencia["semilla"], "")
                    self.assertEqual([fila["semilla"] for fila in geneticos], ["42", "7"])
                    conteos = Counter(fila["resultado_vs_proporcional"] for fila in geneticos)
                    self.assertEqual(sum(map(int, resumen)), 2)
                    self.assertEqual(tuple(map(int, resumen)),
                                     tuple(conteos[clave] for clave in ("gana", "empata", "pierde")))
                    for corrida in filas:
                        clave = corrida["archivo"], corrida["metodo"], corrida["semilla"]
                        productos = [fila for fila in detalle
                                     if (fila["archivo"], fila["metodo"], fila["semilla"]) == clave]
                        self.assertEqual(len(productos), 3)
                        self.assertEqual(sum(int(fila["piezas_recomendadas"]) for fila in productos),
                                         int(corrida["piezas_totales"]))
                        self.assertEqual(sum(int(fila["masa_asignada_g"]) for fila in productos),
                                         int(corrida["masa_usada_g"]))
                        self.assertEqual(int(corrida["masa_disponible_g"]),
                                         int(corrida["masa_usada_g"]) + int(corrida["masa_sobrante_g"]))
                        for fila in productos:
                            self.assertEqual(int(fila["demanda"]),
                                             int(fila["piezas_recomendadas"]) + int(fila["piezas_pendientes"]))
                            if fila["demanda"] == "0":
                                self.assertEqual(fila["cobertura_pct"], "")
                    for corrida in geneticos:
                        self.assertEqual(corrida["poblacion"], "8")
                        self.assertEqual(corrida["generaciones_configuradas"], "5")
                        self.assertEqual(corrida["torneo"], "2")
                        self.assertEqual(float(corrida["prob_cruce"]), 1)
                        self.assertEqual(float(corrida["prob_mutacion"]), 0.25)
                        self.assertEqual(corrida["elitismo"], "1")
                        historial = [fila for fila in evolucion
                                     if fila["archivo"] == archivo and fila["semilla"] == corrida["semilla"]]
                        ejecutadas = 0 if archivo == "masa_suficiente.json" else 5
                        self.assertEqual(int(corrida["generaciones_ejecutadas"]), ejecutadas)
                        self.assertEqual([int(fila["generacion"]) for fila in historial],
                                         list(range(ejecutadas + 1)))
                        aptitudes = [aptitud(fila) for fila in historial]
                        self.assertEqual(aptitudes, sorted(aptitudes))
                        self.assertEqual(aptitudes[-1], aptitud(corrida))
                        valor, base = aptitud(corrida), aptitud(referencia)
                        diferencia = next((
                            campo for campo, actual, anterior in
                            zip(("cobertura_minima", "piezas_totales", "masa_usada_g"), valor, base)
                            if actual != anterior
                        ), "")
                        ganador = "gana" if valor > base else "pierde" if valor < base else "empata"
                        self.assertEqual(corrida["criterio_decisivo"], diferencia)
                        self.assertEqual(corrida["resultado_vs_proporcional"], ganador)

            contenido_anterior = [(destino / archivo).read_bytes() for archivo in ARCHIVOS]
            nuevo = invocar(*argumentos)
            self.assertEqual(nuevo.returncode, 0, nuevo.stderr)
            self.assertEqual(contenido_anterior, [(destino / archivo).read_bytes() for archivo in ARCHIVOS])

    def test_cobertura_sin_demanda_se_muestra_nd_y_se_exporta_vacia(self):
        datos = Path("datos") / "casos_limite"
        salida = invocar("optimizar", datos / "toda_demanda_cero.json")
        self.assertEqual(salida.returncode, 0, salida.stderr)
        self.assertIn("Plan óptimo calculado directamente", salida.stdout)
        self.assertIn("Cobertura mínima  N/D", salida.stdout)
        self.assertIn("Cobertura total   N/D", salida.stdout)
        with tempfile.TemporaryDirectory() as carpeta:
            salida = invocar("comparar", datos, "--semillas", 42, "--generaciones", 0, "--salida", carpeta)
            self.assertEqual(salida.returncode, 0, salida.stderr)
            corridas = leer_csv(Path(carpeta) / "corridas.csv")
            archivos = Counter(fila["archivo"] for fila in corridas)
            self.assertEqual(archivos["toda_demanda_cero.json"], 2)
            self.assertEqual(archivos["masa_cero.json"], 2)
            for fila in corridas:
                if fila["archivo"] == "toda_demanda_cero.json":
                    self.assertEqual(fila["aptitud_minima"], "0/1")
                    self.assertEqual(fila["cobertura_minima_pct"], "")
                    self.assertEqual(fila["cobertura_total_pct"], "")
                    self.assertEqual(fila["masa_sobrante_g"], "10000")
                elif fila["archivo"] == "masa_cero.json":
                    self.assertEqual(fila["cobertura_minima_pct"], "0.00")
                    self.assertEqual(fila["cobertura_total_pct"], "0.00")

    def test_lote_informa_entradas_invalidas_antes_de_iniciar_corridas(self):
        with tempfile.TemporaryDirectory() as carpeta:
            entradas = Path(carpeta)
            contenido = (RAIZ / "datos" / "masa_suficiente.json").read_bytes()
            (entradas / "a_valido.json").write_bytes(contenido)
            (entradas / "b_invalido.json").write_text("{", encoding="utf-8")
            (entradas / "c_invalido.json").write_bytes(contenido.replace(b"13000", b"-1"))
            destino = entradas / "resultados"
            salida = invocar("comparar", entradas, "--semillas", 42, "--salida", destino)
            self.assertNotEqual(salida.returncode, 0)
            self.assertIn("b_invalido.json", salida.stderr)
            self.assertIn("c_invalido.json", salida.stderr)
            self.assertIn("masa_disponible_g", salida.stderr)
            self.assertEqual(salida.stdout, "")
            self.assertFalse(destino.exists())

            salida = invocar("optimizar", entradas / "b_invalido.json")
            self.assertNotEqual(salida.returncode, 0)
            self.assertIn("b_invalido.json", salida.stderr)
            self.assertIn("JSON inválido", salida.stderr)

    def test_terminal_indica_como_corregir_configuracion_y_carpetas(self):
        salida = invocar("optimizar", "datos/escasez_moderada.json", "--prob-cruce", "nan")
        self.assertNotEqual(salida.returncode, 0)
        self.assertIn("número finito entre 0 y 1", salida.stderr)
        with tempfile.TemporaryDirectory() as carpeta:
            vacia = invocar("comparar", carpeta)
            ausente = invocar("comparar", Path(carpeta) / "ausente")
            self.assertNotEqual(vacia.returncode, 0)
            self.assertNotEqual(ausente.returncode, 0)
            self.assertIn("Agrega al menos un escenario", vacia.stderr)
            self.assertIn("Indica la carpeta de escenarios", ausente.stderr)
