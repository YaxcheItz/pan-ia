# Optimización de la producción de pan mediante algoritmos genéticos

Prototipo de Inteligencia Artificial del grupo 9SA del Instituto Tecnológico de Oaxaca. Recomienda cuántas piezas producir en una jornada a partir de la masa común disponible, el consumo por pieza y la demanda de cada producto. Requiere Python 3.10 o posterior y un navegador para el panel. Usa la biblioteca estándar y funciona sin conexión.

## Panel para la exposición

En Windows, haz doble clic en [Abrir interfaz.cmd](<Abrir interfaz.cmd>) o ejecútalo desde PowerShell en la carpeta del proyecto.

```powershell
& ".\Abrir interfaz.cmd"
```

El lanzador abre `http://127.0.0.1:8765/`, reutiliza el servidor si sigue activo y permite cerrar la terminal. El servidor se cierra tras 30 minutos sin solicitudes. También puedes usar `python -m pan_optimizador interfaz` desde una terminal y pulsar `Ctrl+C` para cerrarlo.

1. Abre **Escasez moderada con 10 kg**. Con la semilla 42, el plan recomienda 106 piezas, usa 9 980 g y deja 20 g.
2. Revisa **Plan por producto** y **Evolución del algoritmo**. La vista **Cambios por generación** muestra la población inicial y las mejoras. En **Gráfica**, puedes elegir una métrica, recorrer generaciones y activar **Ver corrida completa**.
3. En **Parámetros del algoritmo**, cambia la semilla a 84 y pulsa **Aplicar cambios**. El plan alcanza 88 % de cobertura mínima en la generación 4 con la semilla 42 y en la 5 con la 84, con los parámetros iniciales. Usa **Pantalla completa** para proyectar.

Puedes editar la masa o abrir **Editar productos** para cambiar datos y agregar o quitar panes. **Personalizado** inicia un formulario vacío. **Restaurar datos del escenario** recupera la masa y los productos de origen. **Mostrar casos límite** añade cuatro escenarios al selector.

La semilla inicializa los sorteos del algoritmo. Repite la semilla, los datos, los parámetros y la versión de Python para reproducir la evolución. Con cero generaciones, la búsqueda selecciona el mejor plan de la población inicial.

## Ejecutar en terminal

Ejecuta los comandos desde la carpeta del proyecto. En Windows también puedes usar `py -3`.

```powershell
python -m pan_optimizador optimizar datos/escasez_moderada.json --semilla 42
python -m pan_optimizador comparar datos --semillas 7 21 42 84 123 --salida resultados
python -B -m unittest discover -s tests -v
```

`optimizar` muestra el plan por producto, sus coberturas y el reparto de referencia. `comparar` genera los CSV de corridas, detalle por producto y evolución. El comando de pruebas verifica el modelo, los algoritmos, el servidor y la terminal.

Usa `--help` en cada comando para ver sus opciones. `optimizar` y `comparar` aceptan `--poblacion`, `--generaciones`, `--torneo`, `--prob-cruce` y `--prob-mutacion`. Sus valores iniciales son 80, 160, 3, 0.85 y 0.15, respectivamente. El elitismo conserva un plan.

## Escenarios JSON

Cada archivo UTF-8 contiene `escenario`, `masa_disponible_g` y una lista `productos` con `nombre`, `gramos_por_pieza` y `demanda` por producto. La masa y la demanda son enteros desde cero. Los gramos por pieza son enteros positivos. El orden de la lista define las posiciones del vector y de la tabla.

El comando `comparar` lee los JSON directamente dentro de la carpeta indicada. En `datos/` están los cuatro escenarios del anteproyecto. En `datos/casos_limite/` están masa exacta, masa cero, toda la demanda en cero y un solo producto.

```powershell
python -m pan_optimizador comparar datos/casos_limite --semillas 7 21 42 84 123 --salida resultados_limite
```

## Métodos

La aptitud prioriza la cobertura del producto menos atendido, luego el total de piezas y por último los gramos usados. Se comparan fracciones exactas de piezas producidas entre demanda. Los productos con demanda cero se excluyen del cálculo de la cobertura mínima.

- **Reparto proporcional.** Aplica a cada demanda la proporción de masa disponible respecto de la masa necesaria y redondea hacia abajo. Redistribuye el sobrante de una pieza a la vez entre los productos pendientes que caben. Tiene prioridad la menor cobertura, después la pieza más ligera y finalmente el orden del JSON.
- **Algoritmo genético.** Arranca con el vector de ceros, las cuotas proporcionales redondeadas hacia abajo y candidatos aleatorios. Evoluciona mediante torneos, cruce en un punto interior, mutación local, reparación y elitismo. La redistribución proporcional se ejecuta de forma independiente como referencia. Si toda la demanda cabe o ninguna pieza puede producirse, el algoritmo devuelve directamente la solución y registra solo la generación 0.

Las pruebas incluyen una enumeración de planes factibles para contrastar los resultados del genético en escenarios pequeños.

## Registros de la comparación

El lote de demostración usa cuatro escenarios y cinco semillas distintas. Los CSV se regeneran con `comparar`. Se escriben en UTF-8 con punto decimal y una celda vacía para las coberturas que aparecen como `N/D` en el panel y en la consola.

| Archivo | Contenido | Filas de la demostración |
| --- | --- | ---: |
| `corridas.csv` | Una fila por escenario, método y semilla. Incluye configuración, aptitud exacta, métricas y comparación contra el reparto. | 24 |
| `detalle_productos.csv` | Una fila por producto de cada plan, con piezas, gramos y cobertura. | 72 |
| `evolucion.csv` | Mejor aptitud de cada generación del genético, incluida la generación 0. | 2 420 |

El reparto proporcional tiene la semilla vacía. La columna `aptitud_minima` guarda la fracción exacta, por ejemplo `22/25`.
