"""Datos de entrada, restricciones, aptitud exacta y métricas de un plan."""

import json
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

Vector = tuple[int, ...]
Aptitud = tuple[Fraction, int, int]


@dataclass(frozen=True)
class Producto:
    nombre: str
    gramos_por_pieza: int
    demanda: int


@dataclass(frozen=True)
class Escenario:
    nombre: str
    masa_disponible_g: int
    productos: tuple[Producto, ...]

    @property
    def demanda_total(self) -> int:
        return sum(producto.demanda for producto in self.productos)

    @property
    def masa_para_toda_la_demanda(self) -> int:
        return sum(
            producto.gramos_por_pieza * producto.demanda
            for producto in self.productos
        )

    @property
    def cotas(self) -> Vector:
        return tuple(
            min(producto.demanda, self.masa_disponible_g // producto.gramos_por_pieza)
            for producto in self.productos
        )


@dataclass(frozen=True)
class Plan:
    piezas: Vector
    aptitud: Aptitud


@dataclass(frozen=True)
class Metricas:
    cobertura_minima: Fraction | None
    cobertura_total: Fraction | None
    piezas_totales: int
    masa_usada_g: int
    masa_sobrante_g: int


def _nombre(valor: object, campo: str) -> str:
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError(f"Escribe un nombre de texto no vacío en «{campo}».")
    return valor.strip()


def _entero(valor: object, campo: str, minimo: int) -> int:
    # bool es una subclase de int y se rechaza en los datos de entrada.
    if type(valor) is not int or valor < minimo:
        raise ValueError(f"«{campo}» debe ser un entero mayor o igual a {minimo}.")
    return valor


def validar_escenario(datos: object) -> Escenario:
    if not isinstance(datos, dict):
        raise ValueError("El documento debe ser un objeto JSON con los datos del escenario.")
    nombre = _nombre(datos.get("escenario"), "escenario")
    masa = _entero(datos.get("masa_disponible_g"), "masa_disponible_g", 0)
    entradas = datos.get("productos")
    if not isinstance(entradas, list) or not entradas:
        raise ValueError("«productos» debe ser una lista con al menos un producto.")

    productos = []
    nombres = set()
    for indice, entrada in enumerate(entradas):
        campo = f"productos[{indice}]"
        if not isinstance(entrada, dict):
            raise ValueError(f"«{campo}» debe ser un objeto con nombre, gramos por pieza y demanda.")
        producto = _nombre(entrada.get("nombre"), f"{campo}.nombre")
        clave = producto.casefold()
        if clave in nombres:
            raise ValueError(f"Usa un nombre único en «{campo}.nombre». «{producto}» está duplicado.")
        nombres.add(clave)
        gramos = _entero(entrada.get("gramos_por_pieza"), f"{campo}.gramos_por_pieza", 1)
        demanda = _entero(entrada.get("demanda"), f"{campo}.demanda", 0)
        productos.append(Producto(producto, gramos, demanda))
    return Escenario(nombre, masa, tuple(productos))


def _constante_invalida(constante: str) -> None:
    raise ValueError(f"«{constante}» no es un valor JSON válido. Usa números finitos.")


def leer_escenario(archivo: Path) -> Escenario:
    try:
        datos = json.loads(
            archivo.read_text(encoding="utf-8-sig"), parse_constant=_constante_invalida
        )
        return validar_escenario(datos)
    except json.JSONDecodeError as error:
        raise ValueError(
            f"Archivo «{archivo}». JSON inválido en la línea {error.lineno}, "
            f"columna {error.colno}. Revisa las comillas, llaves y comas."
        ) from error
    except UnicodeError as error:
        raise ValueError(f"Archivo «{archivo}». Guarda el JSON con codificación UTF-8.") from error
    except OSError as error:
        raise ValueError(f"Archivo «{archivo}». Comprueba la ruta y el permiso de lectura.") from error
    except ValueError as error:
        raise ValueError(f"Archivo «{archivo}». {error}") from error


def masa_usada(escenario: Escenario, piezas: Vector) -> int:
    return sum(
        cantidad * producto.gramos_por_pieza
        for producto, cantidad in zip(escenario.productos, piezas)
    )


def evaluar(escenario: Escenario, piezas: Vector) -> Plan:
    if len(piezas) != len(escenario.productos):
        raise ValueError("El plan debe tener una cantidad por producto.")
    coberturas = []
    for producto, cantidad in zip(escenario.productos, piezas):
        if type(cantidad) is not int or not 0 <= cantidad <= producto.demanda:
            raise ValueError(f"Las piezas de «{producto.nombre}» deben ser enteras y respetar su demanda.")
        if producto.demanda:
            coberturas.append(Fraction(cantidad, producto.demanda))

    masa = masa_usada(escenario, piezas)
    if masa > escenario.masa_disponible_g:
        raise ValueError("El plan excede la masa disponible.")
    minima = min(coberturas) if coberturas else Fraction(0)
    return Plan(piezas, (minima, sum(piezas), masa))


def medir(escenario: Escenario, plan: Plan) -> Metricas:
    minima, piezas, masa = plan.aptitud
    demanda = escenario.demanda_total
    return Metricas(
        cobertura_minima=minima if demanda else None,
        cobertura_total=Fraction(piezas, demanda) if demanda else None,
        piezas_totales=piezas,
        masa_usada_g=masa,
        masa_sobrante_g=escenario.masa_disponible_g - masa,
    )
