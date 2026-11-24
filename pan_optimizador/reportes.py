"""Presentación en consola y registros UTF-8 de la comparación."""

import csv
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory

from .genetico import ResultadoGenetico
from .modelo import CRITERIOS, Aptitud, Escenario, Plan, comparar_aptitudes, medir

ARCHIVOS_CSV = ("corridas.csv", "detalle_productos.csv", "evolucion.csv")


@dataclass(frozen=True)
class ComparacionEscenario:
    archivo: str
    escenario: Escenario
    proporcional: Plan
    geneticos: tuple[ResultadoGenetico, ...]


def _fraccion(valor: Fraction) -> str:
    return f"{valor.numerator}/{valor.denominator}"


def _porcentaje(valor: Fraction | None, *, en_csv: bool = False) -> str:
    if valor is None:
        return "" if en_csv else "N/D"
    entero, decimal = divmod(round(valor * 10000), 100)
    separador, sufijo = (".", "") if en_csv else (",", " %")
    return f"{entero}{separador}{decimal:02d}{sufijo}"


def _detalle(
    escenario: Escenario, plan: Plan
) -> Iterator[tuple[str, int, int, int, int, int, Fraction | None]]:
    for producto, cantidad in zip(escenario.productos, plan.piezas):
        yield (
            producto.nombre,
            producto.demanda,
            cantidad,
            producto.demanda - cantidad,
            producto.gramos_por_pieza,
            cantidad * producto.gramos_por_pieza,
            producto.cobertura(cantidad),
        )


def _texto_aptitud(escenario: Escenario, aptitud: Aptitud) -> str:
    minima, piezas, masa = aptitud
    cobertura = _porcentaje(minima if escenario.demanda_total else None)
    unidad = "pieza" if piezas == 1 else "piezas"
    return f"{cobertura} de cobertura mínima, {piezas} {unidad}, {masa} g"


def mostrar_optimizacion(
    archivo: str, escenario: Escenario, resultado: ResultadoGenetico, proporcional: Plan
) -> None:
    plan = resultado.plan
    config = resultado.configuracion
    print(f"{escenario.nombre} ({archivo})")
    print(f"Masa disponible  {escenario.masa_disponible_g} g")
    print(f"Semilla  {resultado.semilla}")
    print(
        f"Población {config.poblacion} | Generaciones {config.generaciones} | "
        f"Torneo {config.torneo} | Prob. cruce {config.prob_cruce:g} | "
        f"Prob. mutación {config.prob_mutacion:g} | Elitismo {config.elitismo}"
    )
    print(f"Generaciones ejecutadas  {resultado.generaciones_ejecutadas}")
    print()
    print("Plan óptimo calculado directamente" if resultado.trivial else "Mejor plan encontrado")

    filas = [("Producto", "Demanda", "Piezas", "Pendientes", "g por pieza", "g asignados", "Cobertura")]
    for *valores, cobertura in _detalle(escenario, plan):
        filas.append(tuple(map(str, valores)) + (_porcentaje(cobertura),))
    anchos = [max(map(len, columna)) for columna in zip(*filas)]
    for fila in filas:
        celdas = [fila[0].ljust(anchos[0])]
        celdas.extend(texto.rjust(ancho) for texto, ancho in zip(fila[1:], anchos[1:]))
        print(" | ".join(celdas))

    metricas = medir(escenario, plan)
    print()
    print(f"Cobertura mínima  {_porcentaje(metricas.cobertura_minima)}")
    print(f"Cobertura total   {_porcentaje(metricas.cobertura_total)}")
    print(f"Piezas totales    {metricas.piezas_totales} de {escenario.demanda_total}")
    print(f"Masa usada        {metricas.masa_usada_g} g")
    print(f"Masa sobrante     {metricas.masa_sobrante_g} g")
    print()
    diferencia, criterio = comparar_aptitudes(plan.aptitud, proporcional.aptitud)
    print(f"Reparto proporcional  {proporcional.piezas} ({_texto_aptitud(escenario, proporcional.aptitud)})")
    if criterio:
        print(f"El genético {diferencia} por {CRITERIOS[criterio]}.")
    else:
        print("El genético empata con el reparto proporcional.")


def mostrar_comparacion(caso: ComparacionEscenario) -> None:
    escenario = caso.escenario
    aptitudes = [resultado.plan.aptitud for resultado in caso.geneticos]
    conteo = Counter(comparar_aptitudes(aptitud, caso.proporcional.aptitud)[0] for aptitud in aptitudes)
    print(f"{escenario.nombre} ({caso.archivo})")
    print(f"  Reparto proporcional  {_texto_aptitud(escenario, caso.proporcional.aptitud)}")
    print(f"  Ganan {conteo['gana']} | Empatan {conteo['empata']} | Quedan por debajo {conteo['pierde']}")
    print(f"  Mejor aptitud  {_texto_aptitud(escenario, max(aptitudes))}")
    print(f"  Peor aptitud   {_texto_aptitud(escenario, min(aptitudes))}")


def _filas_corrida(
    caso: ComparacionEscenario,
    corrida: ResultadoGenetico | None,
) -> tuple[tuple, tuple, Plan]:
    escenario = caso.escenario
    identificacion = (caso.archivo, escenario.nombre, "proporcional", "")
    plan = caso.proporcional
    parametros = ("",) * 8
    comparacion = ("", "")
    if corrida is not None:
        identificacion = (caso.archivo, escenario.nombre, "genetico", corrida.semilla)
        plan = corrida.plan
        config = corrida.configuracion
        parametros = (
            config.poblacion, config.generaciones, config.torneo, config.prob_cruce,
            config.prob_mutacion, config.elitismo, corrida.generaciones_ejecutadas,
            "si" if corrida.trivial else "no",
        )
        comparacion = comparar_aptitudes(plan.aptitud, caso.proporcional.aptitud)

    metricas = medir(escenario, plan)
    fila = (
        *identificacion, escenario.masa_disponible_g, escenario.demanda_total, *parametros,
        _fraccion(plan.aptitud[0]), metricas.piezas_totales, metricas.masa_usada_g,
        _porcentaje(metricas.cobertura_minima, en_csv=True),
        _porcentaje(metricas.cobertura_total, en_csv=True),
        metricas.masa_sobrante_g, *comparacion,
    )
    return identificacion, fila, plan


def guardar_csv(salida: Path, casos: list[ComparacionEscenario]) -> None:
    salida.mkdir(parents=True, exist_ok=True)
    # Prepara los tres registros antes de sustituir los archivos de la corrida anterior.
    with TemporaryDirectory(prefix=".exportacion-", dir=salida) as temporal:
        archivos = [Path(temporal) / nombre for nombre in ARCHIVOS_CSV]
        with (
            archivos[0].open("w", encoding="utf-8", newline="") as corridas,
            archivos[1].open("w", encoding="utf-8", newline="") as detalle,
            archivos[2].open("w", encoding="utf-8", newline="") as evolucion,
        ):
            corridas_csv = csv.writer(corridas)
            detalle_csv = csv.writer(detalle)
            evolucion_csv = csv.writer(evolucion)
            identificacion = ("archivo", "escenario", "metodo", "semilla")
            corridas_csv.writerow((
                *identificacion, "masa_disponible_g", "demanda_total", "poblacion",
                "generaciones_configuradas", "torneo", "prob_cruce", "prob_mutacion", "elitismo",
                "generaciones_ejecutadas", "trivial", "aptitud_minima", "piezas_totales",
                "masa_usada_g", "cobertura_minima_pct", "cobertura_total_pct", "masa_sobrante_g",
                "resultado_vs_proporcional", "criterio_decisivo",
            ))
            detalle_csv.writerow((
                *identificacion, "producto", "demanda", "piezas_recomendadas", "piezas_pendientes",
                "gramos_por_pieza", "masa_asignada_g", "cobertura_pct",
            ))
            evolucion_csv.writerow((
                "archivo", "escenario", "semilla", "generacion",
                "aptitud_minima", "piezas_totales", "masa_usada_g",
            ))
            for caso in casos:
                for corrida in (None, *caso.geneticos):
                    clave, fila, plan = _filas_corrida(caso, corrida)
                    corridas_csv.writerow(fila)
                    for *producto, cobertura in _detalle(caso.escenario, plan):
                        detalle_csv.writerow((*clave, *producto, _porcentaje(cobertura, en_csv=True)))
                    if corrida is not None:
                        for generacion, (minima, piezas, masa) in enumerate(corrida.historial):
                            evolucion_csv.writerow((
                                caso.archivo, caso.escenario.nombre, corrida.semilla,
                                generacion, _fraccion(minima), piezas, masa,
                            ))
        for archivo in archivos:
            archivo.replace(salida / archivo.name)
