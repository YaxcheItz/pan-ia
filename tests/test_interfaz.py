import json
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import urlopen

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
        self.assertIn("casos_limite/un_producto.json", escenarios)
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
