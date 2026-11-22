import unittest
from fractions import Fraction
from itertools import product
from pathlib import Path
from random import Random

from pan_optimizador.genetico import Configuracion, optimizar, reparar
from pan_optimizador.modelo import Escenario, Producto, leer_escenario, medir
from pan_optimizador.proporcional import cuotas_iniciales, repartir

DATOS = Path(__file__).resolve().parents[1] / "datos"
SEMILLAS = (7, 21, 42, 84, 123)


def optimo_por_enumeracion(escenario):
    """Calcula el control de forma independiente para los escenarios pequeños."""
    demandas = [producto.demanda for producto in escenario.productos]
    pesos = [producto.gramos_por_pieza for producto in escenario.productos]
    rangos = [range(min(demanda, escenario.masa_disponible_g // peso) + 1)
              for demanda, peso in zip(demandas, pesos)]
    mejor = None
    for piezas in product(*rangos):
        masa = sum(peso * cantidad for peso, cantidad in zip(pesos, piezas))
        if masa <= escenario.masa_disponible_g:
            minima = min(
                (Fraction(cantidad, demanda) for cantidad, demanda in zip(piezas, demandas) if demanda),
                default=Fraction(0),
            )
            aptitud = (minima, sum(piezas), masa)
            if mejor is None or aptitud > mejor:
                mejor = aptitud
    return mejor


class AlgoritmosTest(unittest.TestCase):
    def assert_factible(self, escenario, piezas):
        self.assertEqual(len(piezas), len(escenario.productos))
        masa = 0
        for producto, cantidad in zip(escenario.productos, piezas):
            self.assertIs(type(cantidad), int)
            self.assertGreaterEqual(cantidad, 0)
            self.assertLessEqual(cantidad, producto.demanda)
            masa += cantidad * producto.gramos_por_pieza
        self.assertLessEqual(masa, escenario.masa_disponible_g)

    def test_configuracion_valida_limites_y_probabilidades(self):
        Configuracion(poblacion=2, generaciones=0, torneo=2, prob_cruce=0, prob_mutacion=1)
        for argumentos, opcion in (
            ({"poblacion": 1}, "--poblacion"),
            ({"generaciones": -1}, "--generaciones"),
            ({"torneo": 1}, "--torneo"),
            ({"torneo": 81}, "--torneo"),
            ({"prob_cruce": float("nan")}, "--prob-cruce"),
            ({"prob_cruce": float("inf")}, "--prob-cruce"),
            ({"prob_cruce": 1.01}, "--prob-cruce"),
            ({"prob_mutacion": -0.01}, "--prob-mutacion"),
        ):
            with self.subTest(argumentos=argumentos):
                with self.assertRaisesRegex(ValueError, opcion):
                    Configuracion(**argumentos)

    def test_reparacion_ajusta_cotas_y_exceso_conjunto(self):
        escenario = leer_escenario(DATOS / "escasez_moderada.json")
        self.assertEqual(reparar(escenario, (-4, 2, 1000), Random(7)), (0, 2, 25))
        original = escenario.cotas
        self.assertEqual(original, (60, 35, 25))
        for semilla in SEMILLAS:
            with self.subTest(semilla=semilla):
                reparado = reparar(escenario, original, Random(semilla))
                self.assert_factible(escenario, reparado)
                self.assertTrue(all(nuevo <= previo for nuevo, previo in zip(reparado, original)))
                self.assertNotEqual(reparado, original)
        with self.assertRaisesRegex(ValueError, "gen por producto"):
            reparar(escenario, (1,), Random(7))

    def test_cuotas_iniciales_son_independientes_de_la_redistribucion(self):
        escenario = leer_escenario(DATOS / "escasez_moderada.json")
        config = Configuracion(poblacion=2, generaciones=0, torneo=2)
        self.assertEqual(cuotas_iniciales(escenario), (53, 30, 22))
        self.assertEqual(optimizar(escenario, 42, config).plan.piezas, (53, 30, 22))
        self.assertEqual(repartir(escenario).piezas, (53, 31, 22))

    def test_reparto_prefiere_menor_cobertura_y_luego_orden_de_entrada(self):
        equilibrio = Escenario("Cobertura", 100, (Producto("A", 30, 3), Producto("B", 70, 1)))
        mismo_peso = Escenario("Orden", 70, (Producto("Z", 40, 1), Producto("A", 40, 1)))
        self.assertEqual(repartir(equilibrio).piezas, (1, 1))
        self.assertEqual(repartir(mismo_peso).piezas, (1, 0))

    def test_misma_semilla_mismo_historial_y_aptitud_monotona(self):
        escenario = leer_escenario(DATOS / "escasez_moderada.json")
        config = Configuracion(
            poblacion=10, generaciones=18, torneo=3, prob_cruce=1, prob_mutacion=1
        )
        primero = optimizar(escenario, 42, config)
        self.assertEqual(primero, optimizar(escenario, 42, config))
        self.assertFalse(primero.trivial)
        self.assertEqual(primero.generaciones_ejecutadas, 18)
        self.assertEqual(len(primero.historial), 19)
        self.assertEqual(primero.historial, tuple(sorted(primero.historial)))
        self.assertEqual(primero.historial[-1], primero.plan.aptitud)

    def test_planes_triviales_solo_registran_generacion_cero(self):
        casos = (
            ("masa_suficiente.json", (60, 35, 25), 11300, 1700),
            ("casos_limite/masa_exacta.json", (60, 35, 25), 11300, 0),
            ("casos_limite/masa_cero.json", (0, 0, 0), 0, 0),
            ("casos_limite/toda_demanda_cero.json", (0, 0, 0), 0, 10000),
        )
        for ruta, esperado, usada, sobrante in casos:
            with self.subTest(ruta=ruta):
                escenario = leer_escenario(DATOS / ruta)
                referencia = repartir(escenario)
                corrida = optimizar(escenario, 7)
                self.assert_factible(escenario, referencia.piezas)
                self.assert_factible(escenario, corrida.plan.piezas)
                self.assertEqual(corrida.plan.piezas, esperado)
                self.assertEqual(corrida.plan, referencia)
                self.assertTrue(corrida.trivial)
                self.assertEqual(corrida.generaciones_ejecutadas, 0)
                self.assertEqual(corrida.historial, (corrida.plan.aptitud,))
                metricas = medir(escenario, corrida.plan)
                self.assertEqual((metricas.masa_usada_g, metricas.masa_sobrante_g), (usada, sobrante))
        sin_piezas = Escenario("Sin piezas que quepan", 79, (Producto("A", 80, 5),))
        self.assertTrue(optimizar(sin_piezas, 7).trivial)

    def test_factibilidad_y_calidad_frente_a_referencias_exactas(self):
        controles = (
            ("escasez_moderada.json", (53, 31, 22), (Fraction(22, 25), 106, 9980)),
            ("escasez_extrema.json", (1, 0, 0), (Fraction(0), 1, 120)),
            ("demanda_cero_producto_b.json", (24, 0, 9), (Fraction(11, 30), 32, 2960)),
            ("casos_limite/un_producto.json", (3,), (Fraction(3, 5), 3, 240)),
        )
        for ruta, vector_reparto, aptitud_optima in controles:
            with self.subTest(ruta=ruta):
                escenario = leer_escenario(DATOS / ruta)
                self.assertEqual(optimo_por_enumeracion(escenario), aptitud_optima)
                reparto = repartir(escenario)
                self.assert_factible(escenario, reparto.piezas)
                self.assertEqual(reparto.piezas, vector_reparto)
                aciertos = 0
                for semilla in SEMILLAS:
                    corrida = optimizar(escenario, semilla)
                    self.assert_factible(escenario, corrida.plan.piezas)
                    self.assertFalse(corrida.trivial)
                    self.assertLessEqual(corrida.plan.aptitud, aptitud_optima)
                    aciertos += corrida.plan.aptitud == aptitud_optima
                self.assertGreater(aciertos, 0, f"{aciertos}/{len(SEMILLAS)} semillas alcanzaron el control")
