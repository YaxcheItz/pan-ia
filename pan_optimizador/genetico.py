"""Población de vectores enteros, reparación, evolución y elitismo."""

from dataclasses import dataclass
from random import Random
from typing import ClassVar

from .modelo import Aptitud, Escenario, Plan, Vector, evaluar, masa_usada
from .proporcional import cuotas_iniciales

@dataclass(frozen=True)
class Configuracion:
    poblacion: int = 80
    generaciones: int = 160
    torneo: int = 3
    prob_cruce: float = 0.85
    prob_mutacion: float = 0.15
    elitismo: ClassVar[int] = 1

    def __post_init__(self) -> None:
        if type(self.poblacion) is not int or self.poblacion < 2:
            raise ValueError("«--poblacion» debe ser un entero mayor o igual a 2.")
        if type(self.generaciones) is not int or self.generaciones < 0:
            raise ValueError("«--generaciones» debe ser un entero mayor o igual a 0.")
        if type(self.torneo) is not int or not 2 <= self.torneo <= self.poblacion:
            raise ValueError("«--torneo» debe ser un entero entre 2 y el tamaño de la población.")
        for opcion, probabilidad in (
            ("--prob-cruce", self.prob_cruce),
            ("--prob-mutacion", self.prob_mutacion),
        ):
            if type(probabilidad) not in (float, int) or not 0 <= probabilidad <= 1:
                raise ValueError(f"«{opcion}» debe ser un número finito entre 0 y 1.")


@dataclass(frozen=True)
class ResultadoGenetico:
    plan: Plan
    semilla: int
    configuracion: Configuracion
    historial: tuple[Aptitud, ...]
    trivial: bool

    @property
    def generaciones_ejecutadas(self) -> int:
        return len(self.historial) - 1


def reparar(escenario: Escenario, candidato: Vector, rng: Random) -> Vector:
    cotas = escenario.cotas
    if len(candidato) != len(cotas):
        raise ValueError("El candidato debe tener un gen por producto.")
    piezas = [max(0, min(gen, cota)) for gen, cota in zip(candidato, cotas)]
    exceso = masa_usada(escenario, tuple(piezas)) - escenario.masa_disponible_g
    while exceso > 0:
        positivos = [indice for indice, cantidad in enumerate(piezas) if cantidad > 0]
        indice = rng.choice(positivos)
        gramos = escenario.productos[indice].gramos_por_pieza
        reduccion = min(piezas[indice], (exceso + gramos - 1) // gramos)
        piezas[indice] -= reduccion
        exceso -= reduccion * gramos
    return tuple(piezas)


def _mutar(piezas: Vector, cotas: Vector, probabilidad: float, rng: Random) -> Vector:
    genes = list(piezas)
    for indice, (cantidad, cota) in enumerate(zip(piezas, cotas)):
        if cota and rng.random() < probabilidad:
            salto = max(1, cota // 20)
            inferior = max(0, cantidad - salto)
            superior = min(cota, cantidad + salto)
            # Sortea todos los vecinos del intervalo excepto la cantidad actual.
            vecino = rng.randrange(inferior, superior)
            if vecino >= cantidad:
                vecino += 1
            genes[indice] = vecino
    return tuple(genes)


def _cruzar(
    primero: Vector, segundo: Vector, probabilidad: float, rng: Random
) -> tuple[Vector, Vector]:
    if len(primero) < 2 or rng.random() >= probabilidad:
        return primero, segundo
    corte = rng.randrange(1, len(primero))
    return primero[:corte] + segundo[corte:], segundo[:corte] + primero[corte:]


def _mejor(poblacion: list[Plan]) -> Plan:
    return max(poblacion, key=lambda plan: plan.aptitud)


def optimizar(
    escenario: Escenario, semilla: int, configuracion: Configuracion = Configuracion()
) -> ResultadoGenetico:
    cotas = escenario.cotas
    if not any(cotas) or escenario.masa_para_toda_la_demanda <= escenario.masa_disponible_g:
        plan = evaluar(escenario, cotas)
        return ResultadoGenetico(plan, semilla, configuracion, (plan.aptitud,), trivial=True)

    rng = Random(semilla)
    vectores = [(0,) * len(cotas), cuotas_iniciales(escenario)]
    vectores.extend(
        tuple(rng.randint(0, cota) for cota in cotas)
        for _ in range(configuracion.poblacion - len(vectores))
    )
    poblacion = [evaluar(escenario, reparar(escenario, vector, rng)) for vector in vectores]
    mejor = _mejor(poblacion)
    historial = [mejor.aptitud]

    for _ in range(configuracion.generaciones):
        siguiente = [mejor]
        while len(siguiente) < configuracion.poblacion:
            padre = _mejor(rng.sample(poblacion, configuracion.torneo))
            madre = _mejor(rng.sample(poblacion, configuracion.torneo))
            hijos = _cruzar(padre.piezas, madre.piezas, configuracion.prob_cruce, rng)
            lugares = configuracion.poblacion - len(siguiente)
            for hijo in hijos[:lugares]:
                mutado = _mutar(hijo, cotas, configuracion.prob_mutacion, rng)
                siguiente.append(evaluar(escenario, reparar(escenario, mutado, rng)))
        poblacion = siguiente
        mejor = _mejor(poblacion)
        historial.append(mejor.aptitud)

    return ResultadoGenetico(mejor, semilla, configuracion, tuple(historial), trivial=False)
