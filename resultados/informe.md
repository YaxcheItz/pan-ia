# Resultados de la optimización de la producción de pan

Inteligencia Artificial · Grupo 9SA · Instituto Tecnológico de Oaxaca

Se ejecutaron cuatro escenarios simulados con las semillas 7, 21, 42, 84 y 123. Se usaron Python 3.14.2, población de 80, 160 generaciones configuradas, torneo de 3 individuos, cruce de 0,85, mutación de 0,15 y elitismo de 1. El registro contiene 20 corridas del algoritmo genético y cuatro del reparto proporcional.

```powershell
python -m pan_optimizador comparar datos --semillas 7 21 42 84 123 --salida resultados
```

## Comparación de los métodos

Cada aptitud muestra la cobertura mínima, el total de piezas y la masa usada, en el orden en que se comparan. Las cinco semillas de cada escenario terminaron con la misma aptitud.

| Escenario | Aptitud del reparto proporcional | Aptitud final del genético | Resultado del genético |
| --- | --- | --- | --- |
| Masa suficiente, 13 000 g | 100,00 %, 120 piezas, 11 300 g | 100,00 %, 120 piezas, 11 300 g | 5 empates. Sobran 1 700 g. |
| Escasez moderada, 10 000 g | 88,00 %, 106 piezas, 9 980 g | 88,00 %, 106 piezas, 9 980 g | 5 empates. Sobran 20 g. |
| Escasez extrema, 150 g | 0,00 %, 1 pieza, 80 g | 0,00 %, 1 pieza, 120 g | 5 victorias por masa utilizada. |
| Demanda cero del producto B, 3 000 g | 36,00 %, 33 piezas, 3 000 g | 36,67 %, 32 piezas, 2 960 g | 5 victorias por cobertura mínima. |

En escasez extrema el reparto asignó una pieza de A y dejó 70 g. El genético asignó una pieza de C y dejó 30 g. Como en ambos planes hay productos con demanda positiva sin atender y solo se produce una pieza, el uso de 120 g frente a 80 g decide la comparación.

Con demanda cero de B, el reparto asignó `(24, 0, 9)` y el genético `(22, 0, 10)`. La menor cobertura del reparto fue la de C, con 9 de 25 piezas (36,00 %). La menor cobertura del genético fue la de A, con 22 de 60 (36,67 %). La cobertura mínima tiene prioridad, por lo que el segundo plan gana produciendo 32 piezas frente a 33. La cobertura de B se registra como `N/D` y el genético deja 40 g.

## Ejemplo de 10 kg para exponer

El vector `(53, 31, 22)` sigue el orden A, B y C del JSON. Cada cantidad multiplicada por sus gramos por pieza da la masa asignada.

| Producto | Demanda | Piezas | Pendientes | Gramos por pieza | Gramos asignados | Cobertura |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| A | 60 | 53 | 7 | 80 | 4 240 | 88,33 % |
| B | 35 | 31 | 4 | 100 | 3 100 | 88,57 % |
| C | 25 | 22 | 3 | 120 | 2 640 | 88,00 % |
| Total | 120 | 106 | 14 |  | 9 980 | 88,33 % |

C fija la cobertura mínima en 22 de 25 piezas (88,00 %). La cobertura total es 106 de 120 (88,33 %). De los 10 000 g quedan 20 g.

## Evolución y comprobación

Las cinco soluciones de masa suficiente cubrieron la demanda por cálculo directo. En cada caso se registró la generación 0. Las otras 15 corridas sí ejecutaron selección, cruce, mutación y reparación durante 160 generaciones.

En escasez extrema, las cinco semillas alcanzaron la aptitud final desde la población inicial. Con demanda cero de B, tres la alcanzaron en la generación 0 y dos en la generación 1. Para los 10 kg, cuatro la alcanzaron en la generación 4 y la semilla 84 en la generación 5. Las pruebas confirmaron por enumeración la aptitud óptima de cada escenario con escasez. Las cinco semillas de cada uno alcanzaron ese valor en el CSV de corridas.

El genético usa como candidato de arranque las cuotas redondeadas hacia abajo. El reparto de referencia aplica además su redistribución del sobrante en una ejecución independiente. En los 10 kg esas cuotas iniciales son `(53, 30, 22)` y el reparto agrega una pieza de B.

El comando de demostración genera 24 filas en `corridas.csv`, 72 en `detalle_productos.csv` y 2 420 en `evolucion.csv`.
