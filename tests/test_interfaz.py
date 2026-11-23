import json
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from pan_optimizador.interfaz import ServidorPanel, _iniciar_en_segundo_plano, _panel_activo


class InterfazTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        servidor = ServidorPanel()
        hilo = threading.Thread(target=servidor.serve_forever, args=(0.05,), daemon=True)
        hilo.start()
        cls.addClassCleanup(servidor.server_close)
        cls.addClassCleanup(hilo.join)
        cls.addClassCleanup(servidor.shutdown)
        cls.puerto = servidor.server_port
        cls.url = f"http://127.0.0.1:{servidor.server_port}"

    def pedir(self, ruta):
        with urlopen(self.url + ruta, timeout=15) as respuesta:
            return respuesta.headers, respuesta.read()

    def pedir_plan(self, identificador, **parametros):
        consulta = urlencode({"escenario": identificador, **parametros})
        _, contenido = self.pedir(f"/api/plan?{consulta}")
        return json.loads(contenido)

    def calcular_edicion(self, **datos):
        peticion = Request(
            self.url + "/api/plan",
            data=json.dumps(datos).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urlopen(peticion, timeout=15) as respuesta:
            return json.load(respuesta)

    def test_servidor_entrega_panel_listado_y_csv(self):
        encabezados, pagina = self.pedir("/")
        self.assertEqual(encabezados.get_content_type(), "text/html")
        self.assertIn("Planificador de producción", pagina.decode("utf-8"))
        for ruta, tipo in (("/panel.css", "text/css"), ("/panel.js", "text/javascript")):
            encabezados, contenido = self.pedir(ruta)
            self.assertEqual(encabezados.get_content_type(), tipo)
            self.assertTrue(contenido)

        _, catalogo = self.pedir("/api/escenarios")
        escenarios = {dato["id"]: dato for dato in json.loads(catalogo)}
        self.assertEqual(len(escenarios), 8)
        self.assertEqual(escenarios["escasez_moderada.json"]["masa_disponible_g"], 10_000)
        self.assertEqual(escenarios["escasez_moderada.json"]["productos"][0]["demanda"], 60)
        self.assertIn("casos_limite/un_producto.json", escenarios)
        _, parametros = self.pedir("/api/configuracion")
        parametros = json.loads(parametros)
        self.assertEqual(parametros["configuracion"]["generaciones"], 160)
        self.assertEqual(parametros["configuracion"]["elitismo"], 1)
        self.assertEqual(parametros["semillas"], [7, 21, 42, 84, 123])
        encabezados, registros = self.pedir("/registros/corridas.csv")
        self.assertIn("attachment", encabezados["Content-Disposition"])
        self.assertIn(b"aptitud_minima", registros)

    def test_el_lanzador_reutiliza_el_servidor_del_proyecto(self):
        self.assertTrue(_panel_activo(self.puerto))
        with patch("pan_optimizador.interfaz.subprocess.Popen") as crear_proceso:
            self.assertEqual(_iniciar_en_segundo_plano(self.puerto), self.puerto)
            crear_proceso.assert_not_called()

    def test_panel_calcula_la_referencia_de_10_kg_y_su_historial(self):
        datos = self.pedir_plan("escasez_moderada.json", semilla=42)
        self.assertEqual([producto["genetico"] for producto in datos["productos"]], [53, 31, 22])
        self.assertEqual([producto["proporcional"] for producto in datos["productos"]], [53, 31, 22])
        plan = datos["genetico"]
        self.assertEqual((plan["piezas_totales"], plan["masa_usada_g"], plan["masa_sobrante_g"]),
                         (106, 9980, 20))
        self.assertEqual((plan["cobertura_minima_pct"], plan["cobertura_total_pct"]), (88, 88.33))
        self.assertEqual(len(plan["historial"]), 161)
        self.assertEqual(plan["historial"][-1]["piezas_totales"], 106)
        self.assertEqual(datos["comparacion"], {"resultado": "empata", "criterio": ""})

    def test_compara_semillas_para_demanda_cero_sin_perder_el_criterio(self):
        datos = self.pedir_plan("demanda_cero_producto_b.json", comparar=1, semilla=21)
        self.assertEqual(datos["genetico"]["piezas_totales"], 32)
        self.assertEqual(datos["proporcional"]["piezas_totales"], 33)
        self.assertEqual(datos["genetico"]["cobertura_minima_pct"], 36.67)
        self.assertEqual(datos["proporcional"]["cobertura_minima_pct"], 36)
        self.assertIsNone(datos["productos"][1]["cobertura_pct"])
        self.assertEqual([fila["semilla"] for fila in datos["semillas"]], [7, 21, 42, 84, 123])
        self.assertTrue(all(fila["resultado"] == "gana" and fila["criterio"] == "cobertura_minima"
                            for fila in datos["semillas"]))

    def test_masa_ajustada_y_cobertura_no_aplicable(self):
        datos = self.pedir_plan("escasez_moderada.json", masa=0)
        self.assertTrue(datos["masa_modificada"])
        self.assertTrue(datos["genetico"]["trivial"])
        self.assertEqual(datos["genetico"]["cobertura_minima_pct"], 0)
        self.assertEqual(len(datos["genetico"]["historial"]), 1)

        sin_demanda = self.pedir_plan("casos_limite/toda_demanda_cero.json")
        self.assertEqual(sin_demanda["genetico"]["masa_sobrante_g"], 10_000)
        self.assertIsNone(sin_demanda["genetico"]["cobertura_minima_pct"])

    def test_edita_peso_demanda_y_agrega_otro_pan(self):
        _, catalogo = self.pedir("/api/escenarios")
        escenario = next(dato for dato in json.loads(catalogo)
                         if dato["id"] == "escasez_moderada.json")
        productos = escenario["productos"]
        productos[0].update(gramos_por_pieza=90, demanda=20)
        productos.append({"nombre": "Concha", "gramos_por_pieza": 75, "demanda": 10})
        for identificador in (escenario["id"], "personalizado"):
            with self.subTest(identificador=identificador):
                datos = self.calcular_edicion(
                    escenario=identificador, productos=productos, masa_disponible_g=10_000,
                )
                self.assertEqual([p["genetico"] for p in datos["productos"]], [20, 35, 25, 10])
                self.assertEqual(datos["productos"][-1]["masa_asignada_g"], 750)
                for metodo in ("genetico", "proporcional"):
                    self.assertEqual(datos[metodo]["masa_usada_g"], 9_050)
                    self.assertEqual(datos[metodo]["masa_sobrante_g"], 950)
        _, catalogo_posterior = self.pedir("/api/escenarios")
        self.assertEqual(catalogo_posterior, catalogo)

    def test_aplica_configuracion_y_semillas_del_panel(self):
        config = {
            "poblacion": 2, "generaciones": 0, "torneo": 2,
            "prob_cruce": 0, "prob_mutacion": 0.25,
        }
        solicitud = {
            "escenario": "escasez_moderada.json", "semilla": 99,
            "configuracion": config, "semillas_comparacion": [9, -7, 9],
        }
        datos = self.calcular_edicion(**solicitud)
        self.assertEqual(datos["configuracion"], {**config, "elitismo": 1})
        self.assertEqual(datos["genetico"]["semilla"], 99)
        self.assertFalse(datos["genetico"]["trivial"])
        self.assertEqual(datos["genetico"]["generaciones_ejecutadas"], 0)
        self.assertEqual(len(datos["genetico"]["historial"]), 1)
        self.assertEqual([fila["semilla"] for fila in datos["semillas"]], [9, -7])
        self.assertEqual([p["genetico"] for p in datos["productos"]], [53, 30, 22])
        config["generaciones"] = 3
        con_rondas = self.calcular_edicion(**solicitud)
        self.assertEqual(con_rondas["genetico"]["generaciones_ejecutadas"], 3)
        self.assertEqual(len(con_rondas["genetico"]["historial"]), 4)

    def test_rechaza_ediciones_invalidas(self):
        for cambios, mensaje in (
            ({"productos": []}, "al menos un producto"),
            ({"productos": [{"nombre": "Pan", "gramos_por_pieza": 0, "demanda": 1}]}, "gramos_por_pieza"),
            ({"configuracion": {"poblacion": 2, "torneo": 3}}, "torneo"),
            ({"configuracion": {"elitismo": 0}}, "parámetros"),
            ({"semillas_comparacion": [7, 2.5]}, "semillas"),
        ):
            with self.subTest(cambios=cambios):
                with self.assertRaises(HTTPError) as error:
                    self.calcular_edicion(escenario="escasez_moderada.json", **cambios)
                with error.exception as respuesta:
                    self.assertEqual(respuesta.code, 400)
                    self.assertIn(mensaje, json.load(respuesta)["error"])

    def test_rechaza_valores_invalidos_y_rutas_ajenas_al_panel(self):
        for identificador, valores, mensaje in (
            ("inexistente.json", {}, "escenario"),
            ("masa_suficiente.json", {"masa": -1}, "mayor o igual a cero"),
            ("masa_suficiente.json", {"semilla": 2.5}, "números enteros"),
        ):
            with self.subTest(identificador=identificador, valores=valores):
                with self.assertRaises(HTTPError) as error:
                    self.pedir_plan(identificador, **valores)
                with error.exception as respuesta:
                    self.assertEqual(respuesta.code, 400)
                    self.assertIn(mensaje, json.load(respuesta)["error"])
        with self.assertRaises(HTTPError) as error:
            self.pedir("/README.md")
        error.exception.close()
        self.assertEqual(error.exception.code, 404)
