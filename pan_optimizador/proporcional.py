"""Reparto proporcional determinista con redistribución del sobrante."""

from fractions import Fraction

from .modelo import Escenario, Plan, Vector, evaluar, masa_usada


def cuotas_iniciales(escenario: Escenario) -> Vector:
    masa_necesaria = escenario.masa_para_toda_la_demanda
    if escenario.masa_disponible_g >= masa_necesaria:
        return tuple(producto.demanda for producto in escenario.productos)
    return tuple(
        producto.demanda * escenario.masa_disponible_g // masa_necesaria
        for producto in escenario.productos
    )


def repartir(escenario: Escenario) -> Plan:
    cuotas = cuotas_iniciales(escenario)
    piezas = list(cuotas)
    sobrante = escenario.masa_disponible_g - masa_usada(escenario, cuotas)

    while True:
        opciones = (
            (Fraction(cantidad, producto.demanda), producto.gramos_por_pieza, indice)
            for indice, (producto, cantidad) in enumerate(zip(escenario.productos, piezas))
            if cantidad < producto.demanda and producto.gramos_por_pieza <= sobrante
        )
        eleccion = min(opciones, default=None)
        if eleccion is None:
            return evaluar(escenario, tuple(piezas))
        _, gramos, indice = eleccion
        piezas[indice] += 1
        sobrante -= gramos
