# Optimización de la producción de pan mediante algoritmos genéticos

Prototipo de Inteligencia Artificial del grupo 9SA del Instituto Tecnológico de Oaxaca. Recomienda cuántas piezas producir en una jornada a partir de la masa común disponible, el consumo por pieza y la demanda estimada de cada producto.

## Panel para la exposición

En Windows, haz doble clic en [Abrir interfaz.cmd](<Abrir interfaz.cmd>) o ejecútalo desde PowerShell en la carpeta del proyecto.

```powershell
& ".\Abrir interfaz.cmd"
```

El navegador abre el panel en `http://127.0.0.1:8765/`. Puedes cerrar la terminal mientras lo usas. Si ya está abierto, el lanzador reutiliza el servidor. Después de 30 minutos sin solicitudes, el servidor se cierra. Para volver a usarlo, abre de nuevo el lanzador. El panel funciona con Python y el navegador, sin conexión a internet.

Para ver los mensajes del servidor en la terminal puedes ejecutar `python -m pan_optimizador interfaz`. En ese modo, `Ctrl+C` cierra el panel.

1. Empieza con **Escasez moderada con 10 kg**. El panel carga la semilla 42 y muestra 106 piezas, 9 980 g usados y 20 g sobrantes. Puedes editar los gramos disponibles o la semilla y pulsar **Calcular plan**.
2. En **Plan por producto**, revisa las cantidades de cada método. En la gráfica de **Evolución del algoritmo** al final, elige la métrica y mueve **Explorar generación**. La generación 0 es la población inicial. La línea continua sigue al mejor plan genético y la línea punteada indica el valor fijo del reparto proporcional.
3. Selecciona la generación 4 y cambia la semilla de 42 a 84. Pulsa **Calcular plan**. Con los parámetros iniciales, la cobertura mínima llega a 88 % en la generación 4 con la semilla 42 y en la 5 con la 84. Usa **Pantalla completa** para proyectar el panel.

Abre **Editar productos** para cambiar nombres, gramos por pieza y demandas, o para agregar y quitar panes. Elige **Personalizado** para empezar con un formulario vacío. Al elegir otro escenario se cargan sus datos. **Restaurar datos del escenario** vuelve a aplicar su masa y sus productos originales.

La semilla inicializa la secuencia de sorteos del algoritmo. Con la misma semilla, los mismos datos y los mismos parámetros, puedes repetir la corrida y ver la misma evolución.

En **Parámetros del algoritmo** puedes ajustar la población, las generaciones, el tamaño del torneo y los porcentajes de cruce y mutación. El elitismo conserva una copia del mejor plan. Si configuras cero generaciones, el genético elige el mejor plan de la población inicial cuando el caso requiere búsqueda.

El selector muestra los cuatro escenarios de demostración y **Personalizado**. Pulsa **Mostrar casos límite** junto a **Escenario** para incorporar esos casos al selector.

## Ejecutar en terminal

Se requiere Python 3.10 o posterior. El proyecto usa la biblioteca estándar. Abre una terminal en la carpeta `proyecto-pan`. En Windows también puedes usar `py -3` en lugar de `python`.

```powershell
python -m pan_optimizador optimizar datos/escasez_moderada.json --semilla 42
python -m pan_optimizador comparar datos --semillas 7 21 42 84 123 --salida resultados
python -m unittest discover -s tests -v
```

El primer comando muestra las piezas recomendadas por producto con sus gramos y coberturas. El segundo compara las semillas con el reparto de referencia y genera los tres CSV en la carpeta elegida. El tercero verifica el modelo, los algoritmos, el servidor local y los comandos de terminal.

Consulta las opciones con `python -m pan_optimizador optimizar --help` y `python -m pan_optimizador comparar --help`. Ambos comandos aceptan `--poblacion`, `--generaciones`, `--torneo`, `--prob-cruce` y `--prob-mutacion`. Sus valores iniciales son 80, 160, 3, 0.85 y 0.15, respectivamente. El elitismo conserva un individuo. Usa punto decimal al escribir las probabilidades.

## Escenarios JSON

Cada archivo UTF-8 contiene `escenario`, `masa_disponible_g` y una lista `productos` con `nombre`, `gramos_por_pieza` y `demanda` por producto. La masa y la demanda son enteros desde cero. Los gramos por pieza son enteros positivos. El orden de la lista define las posiciones del vector y de la tabla.

El comando `comparar` lee los JSON directamente dentro de la carpeta indicada, en orden por archivo. En `datos/` están los cuatro escenarios del anteproyecto. En `datos/casos_limite/` están masa exacta, masa cero, toda la demanda en cero y un solo producto. Puedes probar esa carpeta por separado.

```powershell
python -m pan_optimizador comparar datos/casos_limite --semillas 7 21 42 84 123 --salida resultados_limite
```

## Métodos

La comparación maximiza, en ese orden, la cobertura del producto menos atendido, el total de piezas y los gramos usados. La cobertura se calcula como piezas producidas entre demanda. Se comparan fracciones exactas y se excluyen los productos con demanda cero al calcular la mínima. Los planes con la misma aptitud se eligen de forma estable.

- **Reparto proporcional.** Aplica a cada demanda la proporción de masa disponible respecto de la masa necesaria y redondea hacia abajo. Redistribuye el sobrante de una pieza a la vez entre los productos pendientes que caben. Tiene prioridad la menor cobertura, después la pieza más ligera y finalmente el orden del JSON.
- **Algoritmo genético.** Arranca con el vector de ceros, las cuotas proporcionales redondeadas hacia abajo y candidatos aleatorios. Evoluciona mediante torneos, cruce en un punto interior, mutación local, reparación y elitismo. La redistribución proporcional se ejecuta de forma independiente como referencia. Si toda la demanda cabe o ninguna pieza puede producirse, el algoritmo devuelve directamente la solución y registra solo la generación 0.

La enumeración exhaustiva de los escenarios pequeños está en las pruebas. Sirve para comparar la aptitud observada con la mejor factible. El comando `optimizar` presenta «Mejor plan encontrado» cuando el algoritmo ejecuta la búsqueda.

## Registros de la comparación

El lote de demostración usa cuatro escenarios y cinco semillas distintas. Las semillas repetidas se toman una sola vez, en el orden en que aparecen. Ejecuta `comparar` para generar esos registros cuando necesites revisar o entregar las corridas. Los CSV son UTF-8, usan punto decimal para los porcentajes e identifican cada escenario por el nombre del archivo JSON. Una cobertura sin denominador aparece como `N/D` en consola y como celda vacía en CSV.

| Archivo | Contenido | Filas de la demostración |
| --- | --- | ---: |
| `corridas.csv` | Una fila por escenario, método y semilla. Incluye configuración, aptitud exacta, métricas y comparación contra el reparto. | 24 |
| `detalle_productos.csv` | Una fila por producto de cada plan, con piezas, gramos y cobertura. | 72 |
| `evolucion.csv` | Mejor aptitud de cada generación del genético, incluida la generación 0. | 2 420 |

El reparto proporcional tiene la semilla vacía. La columna `aptitud_minima` guarda una fracción como `22/25`, incluso cuando las métricas de cobertura no aplican y la aptitud interna es `0/1`. Al repetir el lote se regeneran los tres CSV con los resultados de esa ejecución.

La interpretación de la demostración y el ejemplo para exponer están en el [informe de resultados](resultados/informe.md).
