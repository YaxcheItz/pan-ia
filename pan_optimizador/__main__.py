"""Comandos de optimización, comparación e interfaz de demostración."""

import argparse
from pathlib import Path

from .genetico import Configuracion, optimizar
from .modelo import Escenario, leer_escenario
from .proporcional import repartir
from .reportes import (
    ARCHIVOS_CSV,
    ComparacionEscenario,
    guardar_csv,
    mostrar_comparacion,
    mostrar_optimizacion,
)


def _argumentos() -> argparse.ArgumentParser:
    comunes = argparse.ArgumentParser(add_help=False)
    comunes.add_argument("--poblacion", type=int, default=Configuracion.poblacion,
                         help="individuos por generación")
    comunes.add_argument("--generaciones", type=int, default=Configuracion.generaciones,
                         help="pasos de evolución después de la generación inicial")
    comunes.add_argument("--torneo", type=int, default=Configuracion.torneo,
                         help="individuos que compiten por ser padre")
    comunes.add_argument("--prob-cruce", type=float, default=Configuracion.prob_cruce,
                         help="probabilidad de cruce por pareja")
    comunes.add_argument("--prob-mutacion", type=float, default=Configuracion.prob_mutacion,
                         help="probabilidad de mutación por gen")

    parser = argparse.ArgumentParser(
        prog="python -m pan_optimizador",
        description="Distribuye la masa disponible entre los productos de una jornada.",
    )
    comandos = parser.add_subparsers(dest="comando", required=True)
    simple = comandos.add_parser(
        "optimizar", parents=[comunes], formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        help="recomendar un plan para un archivo JSON",
    )
    simple.add_argument("archivo", type=Path, help="archivo JSON del escenario")
    simple.add_argument("--semilla", type=int, default=42, help="semilla del algoritmo genético")

    lote = comandos.add_parser(
        "comparar", parents=[comunes], formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        help="comparar los dos métodos en una carpeta de escenarios",
    )
    lote.add_argument("carpeta", type=Path, help="carpeta que contiene los archivos JSON")
    lote.add_argument("--semillas", type=int, nargs="+", default=[7, 21, 42, 84, 123],
                      help="semillas del algoritmo genético")
    lote.add_argument("--salida", type=Path, default=Path("resultados"), help="carpeta de los CSV")

    panel = comandos.add_parser("interfaz", help="abrir el panel visual de la demostración")
    panel.add_argument("--puerto", type=int, default=0, help="puerto local (0 usa el predeterminado del modo)")
    panel.add_argument("--sin-abrir", action="store_true", help="imprimir la URL sin abrir el navegador")
    modo = panel.add_mutually_exclusive_group()
    modo.add_argument("--segundo-plano", action="store_true", help="usar el panel sin mantener la terminal abierta")
    modo.add_argument("--servidor-local", action="store_true", help=argparse.SUPPRESS)
    return parser


def _leer_lote(carpeta: Path) -> list[tuple[Path, Escenario]]:
    if not carpeta.is_dir():
        raise ValueError(f"«{carpeta}» no es una carpeta accesible. Indica la carpeta de escenarios.")
    archivos = sorted(
        (archivo for archivo in carpeta.glob("*.json") if archivo.is_file()),
        key=lambda archivo: archivo.name,
    )
    if not archivos:
        raise ValueError(f"«{carpeta}» no contiene archivos JSON. Agrega al menos un escenario.")
    escenarios = []
    errores = []
    for archivo in archivos:
        try:
            escenarios.append((archivo, leer_escenario(archivo)))
        except ValueError as error:
            errores.append(str(error))
    if errores:
        raise ValueError("\n".join(errores))
    return escenarios


def _comparar(carpeta: Path, semillas: list[int], salida: Path, config: Configuracion) -> None:
    escenarios = _leer_lote(carpeta)
    semillas_distintas = tuple(dict.fromkeys(semillas))
    casos = []
    for archivo, escenario in escenarios:
        proporcional = repartir(escenario)
        corridas = tuple(optimizar(escenario, semilla, config) for semilla in semillas_distintas)
        caso = ComparacionEscenario(archivo.name, escenario, proporcional, corridas)
        casos.append(caso)
        mostrar_comparacion(caso)
        print()

    guardar_csv(salida, casos)
    print(f"CSV generados en «{salida}»")
    for nombre in ARCHIVOS_CSV:
        print(f"  {nombre}")


def main() -> None:
    parser = _argumentos()
    args = parser.parse_args()
    try:
        if args.comando == "interfaz":
            from .interfaz import ejecutar_panel

            ejecutar_panel(
                args.puerto,
                abrir_navegador=not args.sin_abrir,
                segundo_plano=args.segundo_plano,
                servidor_local=args.servidor_local,
            )
            return

        config = Configuracion(
            args.poblacion, args.generaciones, args.torneo, args.prob_cruce, args.prob_mutacion
        )
        if args.comando == "optimizar":
            escenario = leer_escenario(args.archivo)
            resultado = optimizar(escenario, args.semilla, config)
            mostrar_optimizacion(args.archivo.name, escenario, resultado, repartir(escenario))
        else:
            _comparar(args.carpeta, args.semillas, args.salida, config)
    except ValueError as error:
        parser.error(str(error))
    except OSError as error:
        parser.error(f"Comprueba la ruta y los permisos de la carpeta. {error}")


if __name__ == "__main__":
    main()
