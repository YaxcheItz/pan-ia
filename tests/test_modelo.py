import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

from pan_optimizador.modelo import Escenario, Producto, evaluar, leer_escenario, medir, validar_escenario


class ValidacionTest(unittest.TestCase):
    def setUp(self):
        self.datos = {
            "escenario": "  Simulación  ",
            "masa_disponible_g": 10,
            "productos": [{"nombre": "  Pan  ", "gramos_por_pieza": 2, "demanda": 3}],
        }

    def test_acepta_un_producto_y_recorta_los_nombres(self):
        escenario = validar_escenario(self.datos)
        self.assertEqual(escenario, Escenario("Simulación", 10, (Producto("Pan", 2, 3),)))

    def test_rechaza_campos_de_escenario_invalidos(self):
        for campo, invalidos in (
            ("escenario", (" ", None, 1)),
            ("masa_disponible_g", (-1, 10.0, "10", True)),
            ("productos", ([], {}, ["Pan"])),
        ):
            for valor in invalidos:
                with self.subTest(campo=campo, valor=valor):
                    with self.assertRaisesRegex(ValueError, campo):
                        validar_escenario({**self.datos, campo: valor})
        with self.assertRaisesRegex(ValueError, "objeto JSON"):
            validar_escenario([])

    def test_rechaza_campos_de_producto_invalidos(self):
        original = self.datos["productos"][0]
        for campo, invalidos in (
            ("nombre", (" ", None, 12)),
            ("demanda", (-1, 2.5, "3", False)),
            ("gramos_por_pieza", (0, -1, 2.0, "2", True)),
        ):
            for valor in invalidos:
                with self.subTest(campo=campo, valor=valor):
                    self.datos["productos"] = [{**original, campo: valor}]
                    with self.assertRaisesRegex(ValueError, rf"productos\[0\]\.{campo}"):
                        validar_escenario(self.datos)

    def test_rechaza_nombres_repetidos_tras_recortar_e_ignorar_mayusculas(self):
        self.datos["productos"].append({
            "nombre": "pAN", "gramos_por_pieza": 1, "demanda": 2,
        })
        with self.assertRaisesRegex(ValueError, r"productos\[1\]\.nombre.*duplicado"):
            validar_escenario(self.datos)

    def test_error_identifica_archivo_y_problema(self):
        with tempfile.TemporaryDirectory() as carpeta:
            archivo = Path(carpeta) / "entrada.json"
            casos = (
                (b"{", r"JSON inv.lido en la l.nea 1"),
                (b"\xff", "UTF-8"),
                (b'{"escenario":"Pan","masa_disponible_g":-1}', "masa_disponible_g"),
                (b'{"escenario":"Pan","masa_disponible_g":NaN}', "NaN"),
            )
            for contenido, causa in casos:
                with self.subTest(causa=causa):
                    archivo.write_bytes(contenido)
                    with self.assertRaisesRegex(ValueError, rf"entrada\.json.*{causa}"):
                        leer_escenario(archivo)
            with self.assertRaisesRegex(ValueError, r"ausente\.json.*lectura"):
                leer_escenario(Path(carpeta) / "ausente.json")


class AptitudTest(unittest.TestCase):
    def test_rechaza_planes_no_factibles(self):
        escenario = Escenario("Control", 10, (Producto("A", 5, 2), Producto("B", 3, 1)))
        for vector in ((1,), (True, 0), (1.0, 0), (-1, 0), (3, 0), (2, 1)):
            with self.subTest(vector=vector):
                with self.assertRaises(ValueError):
                    evaluar(escenario, vector)

    def test_mayor_cobertura_minima_gana_aunque_produzca_menos(self):
        escenario = Escenario(
            "Demanda cero de B", 3000,
            (Producto("A", 80, 60), Producto("B", 100, 0), Producto("C", 120, 25)),
        )
        equilibrado = evaluar(escenario, (22, 0, 10))
        proporcional = evaluar(escenario, (24, 0, 9))
        self.assertEqual(equilibrado.aptitud, (Fraction(11, 30), 32, 2960))
        self.assertEqual(proporcional.aptitud, (Fraction(9, 25), 33, 3000))
        self.assertGreater(equilibrado.aptitud, proporcional.aptitud)

    def test_piezas_desempatan_antes_de_considerar_la_masa(self):
        escenario = Escenario(
            "Desempate por piezas", 120,
            (Producto("A", 40, 2), Producto("B", 100, 1), Producto("C", 120, 1)),
        )
        self.assertGreater(evaluar(escenario, (2, 0, 0)).aptitud,
                           evaluar(escenario, (0, 0, 1)).aptitud)

    def test_masa_desempata_a_igual_cobertura_y_piezas(self):
        escenario = Escenario("Desempate por masa", 150, (Producto("A", 80, 1), Producto("B", 120, 1)))
        self.assertGreater(evaluar(escenario, (0, 1)).aptitud, evaluar(escenario, (1, 0)).aptitud)

    def test_distingue_masa_cero_de_demanda_cero(self):
        masa_cero = Escenario("Masa cero", 0, (Producto("A", 80, 1),))
        demanda_cero = Escenario("Demanda cero", 500, (Producto("A", 80, 0),))
        plan_masa_cero = evaluar(masa_cero, (0,))
        plan_demanda_cero = evaluar(demanda_cero, (0,))
        self.assertEqual(plan_masa_cero.aptitud, (Fraction(0), 0, 0))
        self.assertEqual(plan_demanda_cero.aptitud, plan_masa_cero.aptitud)
        self.assertEqual(medir(masa_cero, plan_masa_cero).cobertura_minima, Fraction(0))
        self.assertEqual(medir(masa_cero, plan_masa_cero).cobertura_total, Fraction(0))
        metricas = medir(demanda_cero, plan_demanda_cero)
        self.assertIsNone(metricas.cobertura_minima)
        self.assertIsNone(metricas.cobertura_total)
        self.assertEqual(metricas.masa_sobrante_g, 500)
