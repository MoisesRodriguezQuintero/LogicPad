# LogicPad

Aplicación de escritorio (Linux) para el estudio y trabajo con lógica
proposicional: apuntes con símbolos lógicos, calculadora lógica y
comprobación de argumentos.

LogicPad es una aplicación **nativa de escritorio** construida con
**Python 3.12+** y **PySide6**. No es una aplicación web, no depende
de ningún servidor y funciona completamente de forma local y offline.

---

## 1. Instalación en Linux

### 1.1. Requisitos

* Linux (probado en un entorno Ubuntu/Debian; debería funcionar en
  cualquier distribución con Python 3.12+ y un entorno gráfico X11 o
  Wayland).
* Python 3.12 o superior.
* `pip` y el módulo `venv` (en Debian/Ubuntu: `sudo apt install
  python3-venv python3-pip`).

### 1.2. Pasos

```bash
# 1. Sitúate dentro de la carpeta del proyecto
cd logicpad

# 2. Crea un entorno virtual
python3 -m venv .venv

# 3. Actívalo
source .venv/bin/activate

# 4. Instala las dependencias
pip install -r requirements.txt
```

### 1.3. Ejecutar LogicPad

```bash
python3 main.py
```

Se abrirá la ventana principal de LogicPad con la pantalla de
selección de modo (Editor / Calculadora lógica / LogicPad / Conjuntos /
Funciones / Relaciones).

### 1.4. Windows

Los mismos pasos, con las órdenes de Windows (PowerShell o `cmd`):

```bat
cd logicpad
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

El proyecto no usa nada específico de Linux. Las dependencias son
**PySide6** y **SymPy** (esta última, para factorizar, resolver ecuaciones
y calcular rangos de funciones en los modos Funciones y Relaciones);
todo funciona **sin conexión** una vez instaladas. El entorno virtual
(`.venv`) no forma parte de la entrega: créalo en cada equipo.

### 1.5. Ejecutar los tests

Los motores (`logic/`, `mathexpr/`, `setcalc/`, `discrete/`) tienen
baterías de tests independientes de la interfaz gráfica; las pruebas de
interfaz usan el plugin «offscreen» de Qt, así que no necesitan pantalla:

```bash
pytest
# o, para más detalle:
pytest -v
```

---

## 2. Estructura del proyecto

```
logicpad/
├── main.py                 # Punto de entrada de la aplicación
├── requirements.txt
├── README.md
│
├── ui/                      # Interfaz gráfica (PySide6)
│   ├── main_window.py        # Ventana principal, menú, navegación
│   ├── start_screen.py       # Pantalla inicial de selección de modo
│   ├── editor.py             # Modo Editor
│   ├── calculator.py         # Modo Calculadora lógica
│   ├── proof_pad.py          # Modo LogicPad (argumentos)
│   ├── sets_tab.py           # Conjuntos: diagrama de Venn (panel de datos + operaciones + resultados)
│   ├── sets_mode.py          # Modo Conjuntos: pestañas «Diagrama de Venn» y «Álgebra y demostraciones»
│   ├── set_algebra_tab.py    # Álgebra de conjuntos con elementos y demostraciones
│   ├── functions_tab.py      # Modo Funciones
│   ├── relations_tab.py      # Modo Relaciones (+ relation_graph.py: grafo dirigido)
│   ├── discrete_common.py    # Cálculo en segundo hilo y vista de resultados
│   ├── venn_view.py          # Diagrama de Venn (QGraphicsView/QGraphicsScene)
│   └── widgets.py            # Widgets Qt reutilizables (LogicLineEdit, SymbolPickerButton)
│
├── logic/                   # Motor lógico — SIN dependencias de PySide6
│   ├── tokens.py              # Tipos de token y tablas de símbolos
│   ├── lexer.py                # Analizador léxico
│   ├── parser.py               # Parser recursivo descendente -> AST
│   ├── ast_nodes.py            # Nodos del AST (*)
│   ├── evaluator.py            # Evaluación del AST
│   ├── truth_table.py          # Generación de tablas de verdad
│   ├── equivalence.py          # Comprobación de equivalencia (tabla de verdad)
│   ├── simplifier.py           # Simplificador simbólico basado en reglas
│   └── argument.py             # Premisas + conclusión, comprobación de validez
│
├── mathexpr/                # Motor de expresiones matemáticas — SIN PySide6
│   ├── tokens.py / lexer.py   # Números, identificadores, operadores ASCII/Unicode
│   ├── ast_nodes.py           # Nodos: aritmética, comparaciones, conjuntos, funciones...
│   ├── parser.py              # Parser recursivo descendente (sin eval)
│   ├── environment.py         # Variables, conjuntos y funciones definidas
│   ├── evaluator.py           # Evaluación segura sobre el AST
│   └── session.py             # Sesión: define / asigna / evalúa línea a línea
│
├── setcalc/                 # Motor de conjuntos y diagramas de Venn — SIN PySide6
│   ├── elements.py            # Lectura/formato de elementos ({1, 2, "a"}), números vs cadenas
│   ├── regions.py             # Las 2^n regiones de un diagrama (máscaras)
│   ├── expr.py                # Expresiones A ∪ B, Aᶜ, A △ B...: parser + regiones que forman
│   ├── model.py               # Modelo de datos (conjuntos, cardinales, condiciones)
│   ├── lp.py / solver.py      # Símplex exacto + ramificación: restricciones de cardinales
│   ├── analysis.py            # Modo A (cardinales) y Modo B (elementos) + operaciones
│   ├── report.py              # Textos de resultados y de región (sin Qt)
│   └── venn_geometry.py       # Geometría del diagrama (círculos, regiones, textos)
│
├── discrete/                # Matemática Discreta — SIN PySide6 (ver 4d, 4e y 4f)
│   ├── values.py              # Valores: números, símbolos, pares (a, b), conjuntos anidados, rangos
│   ├── setbuilder.py          # Conjuntos por condición {x ∈ A | x > 2}
│   ├── sexpr.py               # Expresiones de conjuntos con jerarquía (árbol), impresión y evaluación
│   ├── setproofs.py           # Demostraciones: leyes, elementos arbitrarios, tabla de pertenencia
│   ├── setalgebra.py          # Sesión: cálculo paso a paso y demostración de igualdades
│   ├── functions.py           # Funciones: evaluación, composición, inyectiva/sobreyectiva
│   ├── relations_finite.py    # Relaciones finitas: propiedades, equivalencia, clases, órdenes
│   ├── relations_formula.py   # Relaciones por fórmula (SymPy): propiedades, clases, divisibilidad, ≡
│   ├── exact.py / symbolic.py # Evaluación exacta (fracciones) y puente seguro AST → SymPy
│   └── proof.py               # Estructura común Proof/Report (demostrado/refutado/inconcluso)
│
├── models/
│   └── document.py           # Modelo de documento (.logicpad, JSON)
│
├── utils/
│   ├── quick_entry.py         # Lógica pura de conversión de escritura rápida
│   ├── version.py             # APP_VERSION (única fuente del número de versión)
│   ├── shortcuts.py           # Tabla de atajos de lógica (heredada) + ayuda
│   └── symbols.py             # Registro de símbolos por categoría (lógica,
│                               # cuantificadores, conjuntos...) — única fuente
│                               # de verdad para conversión, selector y ayuda
│
└── tests/
    ├── test_lexer.py
    ├── test_parser.py
    ├── test_evaluator.py
    ├── test_truth_table.py
    ├── test_equivalence.py
    ├── test_simplifier.py
    ├── test_argument.py
    ├── test_quick_entry.py    # Atajos heredados + comandos \forall, \in, \cup...
    ├── test_mathexpr_*.py     # Lexer, parser, evaluador y sesión de mathexpr
    ├── test_setcalc_*.py      # Conjuntos: elementos, expresiones, solver (incl. contraste con
    │                          #   fuerza bruta), análisis de ambos modos y geometría
    ├── test_sets_tab_gui.py   # Interfaz del diagrama de Venn (en modo sin pantalla)
    ├── test_discrete_*.py     # Valores, conjuntos y demostraciones, funciones, relaciones (finitas
    │                          #   y por fórmula) e interfaz de los tres modos nuevos
    └── test_mathexpr_discrete_syntax.py  # |x|, ∣, ≡ (mod m), mod, x², 2x y la precedencia de -x^2
```

**(\*) Nota sobre `ast_nodes.py`:** el diseño original sugería llamar a
este archivo `ast.py`. Se ha renombrado a `ast_nodes.py` para no
ensombrecer al módulo `ast` de la biblioteca estándar de Python dentro
del propio paquete `logic`. Es la única desviación respecto a la
estructura de carpetas propuesta; el resto de la estructura se ha
mantenido tal cual.

El paquete `logic/` **no importa PySide6 en ningún momento** y puede
usarse de forma independiente, por ejemplo desde un intérprete de
Python:

```python
from logic.parser import parse
from logic.evaluator import evaluate

expr = parse("p -> q")
evaluate(expr, {"p": True, "q": False})  # False
```

---

## 3. Sintaxis de escritura rápida

| ASCII   | Unicode | Significado          |
|---------|---------|-----------------------|
| `!`     | `¬`     | Negación (NOT)        |
| `&&`    | `∧`     | Conjunción (AND)      |
| `\|\|`  | `∨`     | Disyunción (OR)       |
| `^`     | `⊕`     | Disyunción exclusiva  |
| `->`    | `→`     | Implicación           |
| `<->`   | `↔`     | Bicondicional         |
| `<=>`   | `≡`     | Equivalencia lógica   |

El motor léxico acepta ambas formas indistintamente y pueden mezclarse
libremente en la misma expresión (por ejemplo `!p ∧ q` es válido).

**Conversión en vivo en el Editor / campos de expresión:** la
conversión ocurre justo al completarse una secuencia (por ejemplo, en
cuanto se escribe la segunda `&` de `&&`, o la `>` final de `->`). No
hace falta pulsar espacio ni ninguna otra tecla. Esto es posible sin
ambigüedad porque ninguna secuencia completa es prefijo de otra con un
significado distinto (los estados intermedios como `-`, `<`, `<-`,
`<=`, `&` o `|` nunca son, por sí solos, un operador válido), así que
la conversión nunca se dispara antes de tiempo ni interfiere con la
edición normal del texto.

Las variables proposicionales se escriben en minúscula (`p`, `q`, `r`,
`p1`...). Las constantes lógicas verdadero/falso se escriben `T`/`F`
(ASCII) o `⊤`/`⊥` (Unicode); por eso las mayúsculas sueltas distintas
de `T`/`F` no son válidas como nombre de variable — es una decisión de
diseño para poder distinguir sin ambigüedad variables de constantes.

---

## 4. Símbolos de cuantificadores y teoría de conjuntos

Además de los atajos de puntuación de la sección anterior, LogicPad
admite una **sintaxis de comandos inspirada en LaTeX** (pero sin
pretender ser un parser LaTeX) para cuantificadores y teoría de
conjuntos. Se escriben con una contrabarra seguida del nombre del
comando:

| Comando     | Resultado | Significado           |
| ----------- | --------- | ---------------------- |
| `\forall`   | ∀         | Para todo              |
| `\exists`   | ∃         | Existe                 |
| `\in`       | ∈         | Pertenece              |
| `\notin`    | ∉         | No pertenece           |
| `\cup`      | ∪         | Unión                  |
| `\cap`      | ∩         | Intersección           |
| `\subset`   | ⊂         | Subconjunto            |
| `\subseteq` | ⊆         | Subconjunto o igual    |
| `\supset`   | ⊃         | Superconjunto          |
| `\supseteq` | ⊇         | Superconjunto o igual  |
| `\setminus` | ∖         | Diferencia             |
| `\emptyset` | ∅         | Conjunto vacío         |
| `\times`    | ×         | Producto cartesiano    |
| `\triangle` | △         | Diferencia simétrica   |
| `\complement`| ᶜ        | Complemento (tras el conjunto: `Aᶜ`) |
| `\to`       | →         | Implicación / función de A en B |
| `\mapsto`   | ↦         | Aplicación (f: x ↦ x²) |
| `\le`       | ≤         | Menor o igual          |
| `\ge`       | ≥         | Mayor o igual          |

Estos comandos pertenecen a un sistema **deliberadamente separado**
del de la sección anterior: no reutilizan ni reasignan `|`, `||` ni
ningún otro carácter de puntuación ya usado por la lógica
proposicional, precisamente para que `|` pueda seguir significando
"tal que" en una definición por comprensión como `{x ∈ ℕ | x < 5}`
sin ambigüedad con el `||` de disyunción.

**Cuándo se convierte cada comando.** La mayoría se convierte en
cuanto se completa, igual que `!`, `&&`, etc. Sin embargo, `\subset`
es, letra a letra, el principio de `\subseteq` (y `\supset` lo es de
`\supseteq`): si `\subset` se convirtiera en cuanto se completa, sería
imposible escribir `\subseteq`. Por eso estos dos casos concretos
esperan a que se escriba un delimitador (un espacio, un paréntesis, un
operador, otra contrabarra...) que confirme que el comando no va a
seguir extendiéndose, exactamente igual que el final de un nombre de
macro en LaTeX. Si el delimitador es un espacio, se consume junto con
el comando (`A \subset B` → `A ⊂B`); cualquier otro delimitador se
conserva (`\subset(` → `⊂(`). Esta comprobación de ambigüedad se
calcula automáticamente comparando toda la tabla de comandos, así que
añadir un comando nuevo en el futuro que resulte ser prefijo de otro
se gestiona solo, sin tocar el motor de conversión (ver
`utils/quick_entry.py` y `utils/symbols.py`).

**Botón «Símbolos» del Editor.** Además de escribir los comandos a
mano, el Editor tiene un botón «Símbolos ▾» con un menú organizado en
las categorías *Lógica*, *Cuantificadores* y *Conjuntos*; seleccionar
una entrada la inserta en la posición actual del cursor sin afectar al
resto del documento.

**Arquitectura.** Todos los símbolos (los heredados de lógica y los
nuevos) están centralizados en una única tabla de datos,
`utils/symbols.py`, con un `Symbol` por entrada (`command`, `unicode`,
`name`, `category`). Añadir un símbolo nuevo, o una categoría
matemática completa (relaciones, funciones, álgebra...) pensada para
el futuro, consiste en añadir entradas a esa tabla: ni el motor de
conversión ni el selector de símbolos ni el diálogo de ayuda necesitan
cambios de código. Este sistema de comandos es puramente de
*notación* para el Editor: no forma parte de la gramática que entiende
la Calculadora (`logic/parser.py`), que deliberadamente sigue
limitada a lógica proposicional por ahora.

---

## 4b. Expresiones matemáticas y funciones (pestaña «Expresiones y funciones»)

La Calculadora tiene una cuarta pestaña, **Expresiones y funciones**,
con su propio motor (`mathexpr/`), independiente de Qt y también de
`logic/`. Mantiene una *sesión*: lo que se define en una línea sigue
disponible en las siguientes hasta pulsar «Reiniciar sesión».

```text
f(x) = x^2 + 1        define una función            → Función «f» definida
f(3)                  evalúa                        → 10
f(2) > f(1)           comparación                   → Verdadero
S = {1, 2, 3}         asigna un conjunto
f(S)                  aplica f a cada elemento      → {1, 4, 9}   (= {f(s) | s ∈ S})
{x | x ∈ S, x > 1}    conjunto por comprensión      → {2, 3}
2 ∈ S    S ∪ {7}    A ⊆ B    A × B    A ∖ B       operaciones y relaciones de conjuntos
∀x ∈ S, x > 0         cuantificador acotado         → Verdadero
x < y -> f(x) < f(y)  expresión suelta (no se evalúa si x, y no están definidas)
```

**Qué reconoce el analizador:** números, variables, funciones, `+ - * / ^`,
`= ≠ < > ≤ ≥`, `∈ ∉ ⊂ ⊆ ⊃ ⊇`, `∪ ∩ ∖ ×`, `∅`, `{…}` (enumerados y por
comprensión), `¬ ∧ ∨ ⊕ → ↔` y cuantificadores `∀`/`∃`. No usa `eval()`:
todo se evalúa recorriendo el AST con operaciones explícitas.

**Decisiones y limitaciones (documentadas a propósito):**

* **`^` es potencia en esta pestaña** (como en `x^2`), mientras que en el
  Editor y en las pestañas de lógica proposicional sigue siendo `⊕`. Por eso
  el campo usa un conversor propio (`MATH_CONVERTER`) que no convierte `^`;
  mantiene `!`, `&&`, `||`, `->`, `<->` y añade `<=`→`≤`, `>=`→`≥`, `<>`→`≠`
  (se eligió `<>` y no `!=` para que `!` no sea prefijo de otro atajo).
* **Definir vs. comparar.** `nombre(param) = valor` define una función. Si el
  lado derecho es una comparación, un conector lógico o un cuantificador
  (p. ej. `f(x) = f(y) -> x = y`, la inyectividad), se reconoce como
  expresión. Pero `f(x) = f(y)` *a secas* es sintácticamente idéntica a una
  definición y se interpreta como tal: es una limitación inherente a usar `=`
  para ambas cosas, y por ahora no se evalúan propiedades como la
  inyectividad (solo se *reconocen* estructuralmente).
* Cuantificadores: se evalúan solo sobre un **dominio finito conocido** y con
  cuerpo (`∀x ∈ A, x > 0`). `∀x ∈ A` sin cuerpo se reconoce pero da un error
  claro al evaluarla, en vez de inventar un resultado. Sobre dominio vacío,
  `∀` es verdadero y `∃` falso.
* Funciones de **un solo parámetro**. Comparaciones encadenadas (`a < b < c`)
  no admitidas. Operaciones de conjuntos (`∪ ∩ ∖ ×`) al mismo nivel de
  precedencia, asociativas por la izquierda (simplificación de esta versión).
* **Salvaguardas de robustez:** `0^-1` y `(-8)^0.5` dan un error claro (no
  una excepción ni un número complejo); las potencias enteras cuyo
  resultado superaría ~100.000 bits (p. ej. `9^9^9`) se rechazan en vez de
  dejar la aplicación calculando; y un anidamiento absurdo de paréntesis
  produce un error en lugar de un fallo de recursión.
* Los elementos de un conjunto deben ser números, booleanos o tuplas (no hay
  conjuntos de conjuntos todavía). `{…}` vacío y `∅` son equivalentes.
* **Por qué `mathexpr/` no reutiliza `logic/ast_nodes.py`:** esas clases
  llevan un impresor/precedencia pensado solo para lógica proposicional;
  mezclarlas con nodos de comparación o conjuntos las habría roto y acoplado
  dos módulos pensados para evolucionar por separado. Se reutiliza el
  *patrón* (lexer/parser/AST/evaluador sin Qt), no las clases.

**Pendiente** (el AST ya deja sitio para ello): evaluar propiedades
cuantificadas sobre dominios no enumerados, funciones de varios argumentos,
`↦` como definición (`f: x ↦ x²`; hoy es solo un símbolo), imagen e imagen
inversa de conjuntos más allá de `f(S)`, impresor de expresiones y
autocompletado de comandos mientras se escribe.

---

### Cambios de sintaxis para Matemática Discreta (versión 0.7)

* **Corrección de un error de precedencia**: `-x^2` es −(x²) y `-2^2` es −4
  (antes se leía como (−x)² y daba 4). `(-2)^2` sigue siendo 4 y `2^-1`, 0,5.
* Nuevos atajos: `x²`/`x³`, multiplicación implícita tras un número (`2x`,
  `3(x+1)`), el signo `−` de Unicode, `a mod m`, `a ∣ b` (divide a),
  `a ≡ b (mod m)`, `⇔` y `<=>`, y `·` como producto.
* **Modo fórmula** (relaciones y funciones): `|x|` es el valor absoluto; ahí
  `||` son dos barras, y la disyunción se escribe `∨` (un `&` suelto es `∧`).

---

## 4c. Conjuntos y diagramas de Venn (modo «Conjuntos»)

Cuarto modo de la pantalla de inicio (botón **4. Conjuntos**, o *Ver ▸ Conjuntos*).
Sirve para resolver ejercicios de conjuntos y para explorarlos visualmente.
Funciona con **1, 2 o 3 conjuntos**: con más, un diagrama de Venn clásico deja de
ser legible, así que el botón «＋ Conjunto» se desactiva a partir de 3 (el motor
`setcalc/` admite más, pero la interfaz lo limita explícitamente).

**Distribución.** *Izquierda:* el modo de cálculo y dos secciones plegables,
**Cardinales** (`|U|`, `|A|`, `|B|`, `|C|`… y el botón «Añadir condición» para datos como
`|A ∩ B| = 2` o `|A ∪ B| = 5`) y **Conjuntos** (`U = {…}`, `A = {…}`, renombrar y
eliminar). *Derecha:* selector de operación, diagrama de Venn y panel de resultados.

### Dos modos de cálculo

| | **A · Cardinales** | **B · Conjuntos explícitos** |
|---|---|---|
| Datos | Cantidades y condiciones | Los elementos reales |
| Resultado de una operación | Su **cardinal**, si se deduce | El **conjunto** resultante y su cardinal |
| Cada región es | *Conocida*, *indeterminada* o *incompatible* | Conocida (sus elementos) |

**Modo A.** Cada región del diagrama es una variable entera ≥ 0 y cada dato es una
suma de regiones, p. ej. `|A| = solo_A + solo_AB + solo_AC + solo_ABC`. El programa
**no elige una solución arbitraria**: para cada región calcula el mínimo y el máximo
que alcanza *alguna* distribución válida. Si coinciden, la región es **conocida**; si
no, es **indeterminada** (se muestra «?» y su rango, p. ej. `0–30`, y el panel sugiere
qué datos ayudarían, como `|A ∩ B|`); y si ninguna distribución cumple los datos, son
**incompatibles** (se marca ✗ y se explica *qué condiciones* chocan, p. ej. «`|A ∩ B| = 4`
no puede cumplirse junto con `|A| = 3`: lo primero está contenido en lo segundo»).
El universo se respeta: sin regiones negativas y sin que la unión supere a `|U|`.
Para la unión de 2 o 3 conjuntos se muestra la fórmula de inclusión–exclusión con los
valores sustituidos (`3 + 4 − 2 = 5`) o qué términos faltan para aplicarla.

**Modo B.** Los conjuntos se escriben con sus elementos: `{1, 2, 3}`. Se tratan
matemáticamente: sin duplicados, `2` y `2.0` son el mismo número, y `3` (número) y
`"3"` (cadena entre comillas) son elementos **distintos**; una palabra suelta (`a`) es una
cadena. Un campo en blanco significa «sin definir» y `{}` es el conjunto vacío. Los
cardinales y las regiones se derivan de los elementos. Si un conjunto contiene
elementos que no están en `U`, se avisa (no se aceptan en silencio). Los cardinales de
los conjuntos con elementos están **bloqueados** (se calculan), de modo que no se puede
introducir uno incompatible.

### Operaciones

Se escriben en el campo «Operación» (o se eligen de la lista; las barras de botones
insertan `∪ ∩ ∖ △ ᶜ ( )`, y valen los comandos `\cup \cap \setminus \triangle \complement`):

| Operación | Escritura | | Operación | Escritura |
|---|---|---|---|---|
| Unión | `A ∪ B` | | Complemento (respecto de U) | `Aᶜ` (o `A'`) |
| Intersección | `A ∩ B` | | Diferencia simétrica | `A △ B` |
| Diferencia | `A ∖ B` (o `A \ B`) | | Triple unión / intersección | `A ∪ B ∪ C`, `A ∩ B ∩ C` |

También sirven combinaciones como `(A ∪ B) ∖ C` o `(A ∪ B)ᶜ`, `U` (universo) y `∅`. `∩`
liga más que `∪`; mezclar `∪`, `∖` y `△` sin paréntesis, o encadenar `∖`, se **rechaza**
por ambiguo (hay que usar paréntesis). La operación elegida se **resalta en ámbar** en el
diagrama, y todas las operaciones se calculan sobre las mismas regiones que se dibujan,
así que diagrama y resultados no pueden discrepar.

### Diagrama y regiones

El rectángulo es el universo `U` y cada conjunto es un círculo. En cada región se
muestra su cardinal (o «?» con su rango, o ✗), y en el modo B también sus elementos
entre llaves; si no caben se recortan con «…» (la lista completa está en el panel).
**Haz clic en una región** para ver a qué conjuntos pertenece, su expresión (`A ∩ B ∩ Cᶜ`),
su cardinal (conocido o rango) y sus elementos. Pasar el ratón por encima muestra lo mismo
como *tooltip*. No hay arrastre de círculos ni editor gráfico en esta versión.

### Validaciones

Cardinales enteros no negativos (el campo solo admite dígitos); cardinal de un conjunto
o de una intersección mayor que el de otro que lo contiene, o unión mayor que `|U|`
(contradicciones detectadas por el solver, con su explicación); expresiones con
conjuntos inexistentes o mal formadas; nombres duplicados o reservados (`U`); elementos
fuera de `U`; textos de elementos mal escritos (llaves o comillas sin cerrar, comas de más).
Los datos incompletos o contradictorios nunca bloquean la aplicación.

### Cómo calcula el modo A (para quien quiera saber más)

`setcalc/solver.py` resuelve exactamente el problema *relajado* (valores fraccionarios) con
un símplex de fracciones propio (`setcalc/lp.py`, sin SciPy ni otras dependencias), que
decide la compatibilidad y da las cotas de cada región en tiempo polinómico; si el óptimo
relajado no es entero, ramifica (*branch & bound*) para confirmar o descartar cada valor
entero. Es exacto también con cardinales enormes (p. ej. 10⁹). Hay un límite de trabajo de
seguridad: si se alcanza, las cotas se marcan como aproximadas en lugar de darlas por
exactas. El solver se contrasta en los tests con una enumeración por fuerza bruta de todas
las distribuciones posibles en cientos de casos aleatorios.

### Limitaciones conocidas y pendiente

* Solo condiciones de **igualdad** (`|expr| = n`); aún no desigualdades (`≥`, `≤`).
* Máximo 3 conjuntos en la interfaz; para más habría que usar otra representación (p. ej. un
  diagrama de Edwards o una tabla de regiones), no implementada.
* Sin conjuntos de conjuntos ni producto cartesiano en este modo (para eso, ver 4b).
* En modo B, si falta algún conjunto por definir no se calcula nada (se indica cuáles faltan).
* Sin exportación del diagrama a imagen ni arrastre libre de los círculos.
* El modo «Conjuntos» **todavía no existe en la versión de Android**.

---

## 4d. Conjuntos: álgebra y demostraciones (Conjuntos ▸ «Álgebra y demostraciones»)

Segunda pestaña del modo Conjuntos (la primera es el diagrama de Venn de 4c).

**Definir conjuntos** (una línea por conjunto, `NOMBRE = valor`): por extensión
`A = {1, 2, 3}`; vacío `∅` o `{}`; unitarios `{5}`; **anidados** `{1, {2}, ∅}`;
con **pares ordenados** `{(a, b), (b, a)}`; rangos `{1..10}`; y por condición
`B = {x ∈ U | x mod 2 = 0 ∧ x > 3}` (dominio finito y elementos numéricos; la
condición se evalúa de forma exacta, sin `eval`). La igualdad es **extensional**:
orden y repeticiones no importan, `2` y `2.0` coinciden, `3` y `"3"` no, y
`{1}` (conjunto unitario) no es `1`. Un identificador sin comillas dentro de un
conjunto es un símbolo, salvo que esté definido (`{A, 3}` contiene al conjunto A).

**Operaciones** (se escriben en «Calcular», con resultado paso a paso):
`∪ ∩ ∖ △ ×`, complemento `Aᶜ` / `A'` / `complemento(...)` / barra combinada,
conjunto de partes `𝒫(A)` o `P(A)`, cardinal `|A|`, y las comprobaciones
`=  ≠  ⊆  ⊂  ⊇  ⊃  ∈  ∉` (con explicación; recuerda la diferencia entre
**pertenencia** `{1} ∈ {{1}, 2}` e **inclusión** `{1} ⊆ {1, 2}`, que el programa señala
con los valores reales). Un `x ∈ A` con `x` sin definir trata `x` como un símbolo.

* **El complemento exige el universo `U`**: no se supone ninguno. Si un conjunto
  no está contenido en `U`, se avisa.
* **Jerarquía**: las expresiones se guardan como un **árbol**, no como texto.
  `complemento(A ∪ (B ∩ C))`, `Aᶜ ∪ (B ∩ C)` y `Aᶜ ∩ (Bᶜ ∪ Cᶜ)` son tres
  expresiones distintas. En pantalla el complemento de una expresión completa
  se dibuja con una **barra sobre toda la expresión** (y en texto como
  `(A ∪ (B ∩ C))ᶜ`, con paréntesis explícitos).
* **Límites** (para no bloquear la interfaz): `𝒫(A)` se calcula hasta 12
  elementos (4096 subconjuntos); `A × B` hasta 5000 pares. Por encima se
  muestra el cardinal (2ⁿ o |A|·|B|) y una muestra limitada.
* Los cálculos se hacen en un hilo aparte: la ventana sigue respondiendo.

**Demostrar** una igualdad o inclusión (`A`, `B`, `C` son conjuntos **arbitrarios**,
no los definidos arriba). Métodos:

| Método | Qué hace |
|---|---|
| Leyes del álgebra de conjuntos | Cadena de igualdades justificada (De Morgan, distributiva, asociativa, conmutativa, idempotencia, absorción, complemento doble, definiciones de ∖ y △, neutro, complemento…). Búsqueda por ambos lados; **cada paso se verifica** semánticamente antes de mostrarse. |
| Elementos arbitrarios | `x ∈ L ⇔ … ⇔ x ∈ R`: traduce la pertenencia a lógica y aplica leyes lógicas; si no encuentra la cadena, hace un **análisis por casos** de la pertenencia de x (igualmente completo). |
| Tabla de pertenencia | Los 2ⁿ casos de pertenencia de un elemento arbitrario (hasta 6 conjuntos). Es una demostración completa, no una prueba con ejemplos. |
| Comprobar con mis conjuntos | Verifica con los conjuntos concretos definidos. **No demuestra**: si coinciden, lo dice. |

Si la igualdad es **falsa**, el programa lo detecta y construye un
**contraejemplo concreto** (universo de un elemento y conjuntos que lo
contienen o no). Una igualdad nunca se da por cierta por haber probado ejemplos.
Si la búsqueda de leyes no encuentra cadena, lo dice (sin afirmar que sea falsa) y
las otras dos demostraciones siguen decidiendo.

---

## 4e. Funciones (modo «Funciones»)

**Definir**: `f(x) = x^2 - 1`, `g(x) = 2*x + 5`; a trozos con `si` y `en otro caso`:
`h(x) = x + 1 si x < 0; x^2 si x >= 0` (el primer trozo cuya condición se cumple
manda). Se admiten `+ - * / ^`, valor absoluto `|x|`, `sqrt`, `sin`, `cos`, `tan`, `exp`,
`ln`, `floor`, `ceil`, la constante `pi` (o `π`) y funciones ya definidas.

* **Evaluar** `f(a)`: elige el trozo (explicando por qué), sustituye y muestra los
  cálculos intermedios con aritmética exacta (`f(3) = 3^2 - 1 = 9 - 1 = 8`).
* **Componer** (exterior ∘ interior): `g ∘ f`, `f ∘ g`, `f ∘ f`, `g ∘ g`, también con
  trozos (se combinan las condiciones), mostrando la sustitución y la simplificación.
* **Estudiar** inyectividad, sobreyectividad y biyectividad, con **dominio y
  codominio escritos por ti** (nunca se suponen): `ℝ`, `ℤ`, `ℕ`, `ℤ⁺`, `ℝ⁺`, intervalos
  `[0, ∞)`, `(−1, 3]`, `[−π/2, π/2]`, `ℝ ∖ {0}`, uniones y conjuntos finitos `{1, 2, 3}`.
  Cambiar el dominio cambia el resultado (`x²` es inyectiva en ℕ y no en ℤ).

Cómo se decide cada propiedad (y qué significa cada veredicto):

* **Refutada** con un **contraejemplo exacto** y comprobado (`f(1) = f(−1) = 0`,
  o un `y` del codominio sin preimagen). Nunca se usan valores fuera del dominio.
* **Demostrada** solo con razonamiento simbólico: factorización de `f(a) − f(b)` y
  análisis de las demás raíces, monotonía estricta con la derivada, imágenes de
  cada trozo con SymPy (`function_range`), despeje de `x` en `f(x) = y`, o
  comprobación exhaustiva si el dominio es finito.
* **Inconclusa** cuando no hay ni lo uno ni lo otro. Unos cuantos valores
  evaluados jamás se presentan como demostración.
* Antes se comprueba que `f` esté **bien definida** de D en C (p. ej. `√x` en ℝ no lo
  está) y, si es biyectiva, se calcula la **inversa**.

---

## 4f. Relaciones binarias (modo «Relaciones»)

### Relaciones finitas

Introduce el conjunto `A = {a, b, c}` y la relación `R = {(a,a), (b,b), (c,c), (b,a)}`.
Todo se comprueba sobre los **pares reales de R** (nunca se infieren pares que no
están) y se valida que `R ⊆ A × A`. Para cada propiedad se muestran las
comprobaciones una a una y, si falla, un **contraejemplo concreto**:

reflexiva · irreflexiva · simétrica · antisimétrica · asimétrica · transitiva
(identifica las cadenas `(a,b), (b,c)` y comprueba `(a,c)`) · total/comparabilidad.

Distingue **simetría de antisimetría** (puede ser simétrica sin ser antisimétrica y
al revés; el programa lo señala) e indica los casos que se cumplen **por vacuidad**.
**Equivalencia**: razona cada propiedad por separado, calcula las **clases**, el
**conjunto cociente** y comprueba que forman una partición. **Orden**: parcial,
total, estricto. Además: **matriz** de la relación y **grafo dirigido** (hasta 12
elementos). Los elementos pueden ser pares (relaciones sobre productos).

### Relaciones definidas por fórmula

`Universo: ℝ` y `x R y ⇔ |x| = |y|`. Universos: `ℝ ℚ ℤ ℕ ℤ⁺`, productos `ℝ × ℝ` / `ℤ²`
(con cabecera `(a,b) R (c,d) ⇔ a + d = b + c`), **funciones** (`f R g ⇔ f(0) = g(0)`) o
un conjunto finito. La condición admite álgebra, `|x|`, `= ≠ < > ≤ ≥`, `∣`,
`≡ (mod m)`, `mod`, y `∧ ∨ ¬ ⇒ ⇔`. Para cada propiedad el veredicto es uno de tres:

1. **Refutada** con un contraejemplo **exacto** (aritmética con fracciones) o
   obtenido resolviendo la ecuación y verificado con SymPy.
2. **Demostrada** con un razonamiento válido para **todo** el universo: simplificar
   `x R x`, factorizar (`x² − y² − x + y = (x − y)(x + y − 1)`), reescribir como
   `g(x) = g(y)` y usar la transitividad de la igualdad, la identidad
   `E(x,y) + E(y,z) = E(x,z)`, resolver `E(x,y) = 0` y ver que la otra raíz cae
   fuera del universo, o razonamiento proposicional sobre las condiciones.
3. **Inconclusa**, explicando que no hay contraejemplo en la muestra (lo cual **no es una
   demostración**) ni prueba algebraica.

**Clases de equivalencia**: plantea la ecuación, la pasa a un lado, factoriza y
resuelve (`x² − y² = x − y` y la clase de 5: `(b − 5)(b + 4) = 0`, `[5] = {−4, 5}`),
filtra por el universo, y también da la clase de un elemento genérico `a` (`{a, 1 − a}`).
**Relaciones especiales** con demostraciones teóricas: divisibilidad (en ℤ⁺ es
orden parcial no total; en ℤ no es antisimétrica: `2 ∣ −2` y `−2 ∣ 2`), congruencia
módulo m (reflexiva, simétrica, transitiva a partir de `m ∣ (a − b)`, equivalencia con
`a mod m = b mod m`, clases `[r]` y `ℤ_m`).

En el universo de **funciones** la antisimetría nunca se demuestra con razonamiento
sobre valores (dos funciones distintas pueden coincidir en los puntos de la
condición): se construye un contraejemplo con funciones concretas.

### Limitaciones matemáticas conocidas

* La decisión se apoya en SymPy y en una muestra de valores: relaciones con
  funciones trascendentes u ecuaciones que SymPy no resuelve quedan **inconclusas**.
* La transitividad se demuestra para condiciones del tipo `E(x,y) ⋈ 0` (ecuaciones y
  desigualdades), sus conjunciones y las deducibles por lógica; con disyunciones o
  `≠` solo se refuta o queda inconclusa.
* Las clases se calculan resolviendo ecuaciones en ℝ y filtrando por el universo
  (ℤ, ℕ…); si SymPy no resuelve la ecuación, no se describe la clase.
* Funciones: no hay dominio ℚ; los dominios enteros se demuestran solo para
  funciones de un trozo; las imágenes de trozos que se solapan no se resuelven.
* Conjuntos: la búsqueda de leyes tiene un límite (algunas igualdades con △ solo se
  demuestran por elementos o por tabla); la tabla admite hasta 6 conjuntos.
* El orden/relaciones entre funciones solo usa sus valores en puntos concretos.

---

## 5. Precedencia y asociatividad de operadores

De mayor a menor prioridad de "unión":

1. `¬` (unario)
2. `∧`
3. `⊕`
4. `∨`
5. `→`
6. `↔`
7. `≡` — no es un operador normal: es una afirmación de equivalencia
   entre dos expresiones completas, solo válida en la posición más
   externa de la fórmula (no se puede anidar dentro de un paréntesis
   ni encadenar más de una vez).

Asociatividad (decisión de diseño, ya que el enunciado no la fijaba de
forma explícita):

* `∧`, `⊕`, `∨`, `↔` son asociativos por la **izquierda**.
* `→` es asociativo por la **derecha** (`p → q → r` ≡ `p → (q → r)`),
  siguiendo la convención habitual en los textos de lógica.

---

## 6. Los modos de trabajo

### 6.1. Editor

Editor de texto sencillo para apuntes que mezclan texto normal y
expresiones lógicas, con conversión automática de escritura rápida.
Permite crear, abrir y guardar documentos en el formato propio
`.logicpad` (JSON internamente), además de las operaciones básicas de
edición (deshacer/rehacer, copiar/pegar, seleccionar).

### 6.2. Calculadora lógica

Cuatro pestañas (las tres primeras, de lógica proposicional; la cuarta,
sección 4b):

* **Evaluar y tabla de verdad**: analiza una expresión, detecta sus
  variables automáticamente, permite evaluarla con valores concretos y
  genera su tabla de verdad completa (con opción de ocultar las
  columnas de sub-expresiones intermedias), además de indicar si es
  una tautología, una contradicción o una contingencia.
* **Simplificar**: aplica el simplificador simbólico y muestra, paso a
  paso, qué regla de equivalencia se ha aplicado en cada transformación.
* **Comprobar equivalencia**: compara dos expresiones A y B y
  determina formalmente (por tabla de verdad) si son lógicamente
  equivalentes, mostrando un contraejemplo si no lo son.

### 6.3. LogicPad (modo avanzado)

Permite escribir un argumento completo (premisas + conclusión) y
comprobar su validez formal. Se admiten dos formatos de entrada:

```
p -> q
q -> r
------
p -> r
```

o bien:

```
p -> q
q -> r
∴ p -> r
```

Un argumento es válido si no existe ninguna asignación de valores de
verdad en la que todas las premisas sean verdaderas y la conclusión
sea falsa. La primera versión lo comprueba por fuerza bruta mediante
tabla de verdad.

### 6.4. Conjuntos

Dos pestañas: el diagrama de Venn y calculadora de cardinales (sección 4c) y el
álgebra de conjuntos con demostraciones (sección 4d).

### 6.5. Funciones

Evaluación, composición e inyectividad/sobreyectividad (sección 4e).

### 6.6. Relaciones

Relaciones finitas y por fórmula, equivalencias, clases y órdenes (sección 4f).

---

## 7. Simplificador: reglas implementadas

El simplificador trabaja sobre el AST (nunca sobre texto) y aplica
reglas repetidamente hasta alcanzar un punto fijo. Reglas incluidas en
esta primera versión (cada una con un identificador estable para
poder ampliarlas en el futuro):

* Doble negación
* Leyes de De Morgan
* Identidad
* Dominación
* Idempotencia
* Complementación
* Absorción
* Distributividad (aplicada como factorización, que es la dirección
  que efectivamente simplifica: `(A∧B)∨(A∧C) → A∧(B∨C)`)

**Sobre conmutatividad y asociatividad:** no se implementan como
transformaciones visibles independientes (no tendría sentido mostrar
un paso "`p ∧ q → q ∧ p`" como si fuera una simplificación). En su
lugar, cada regla comprueba el patrón en ambos órdenes de operandos
(conmutatividad), y el motor recorre y simplifica el árbol de forma
recursiva en cualquier nivel de anidamiento (asociatividad). Esta
decisión está documentada también como comentario en
`logic/simplifier.py`.

Cada simplificación puede comprobarse de forma independiente: el test
`test_simplification_preserves_meaning` en
`tests/test_simplifier.py` verifica, usando el comprobador de
equivalencia por tabla de verdad, que el resultado simplificado sigue
siendo equivalente a la expresión original.

---

## 8. Formato de archivo `.logicpad`

Formato JSON sencillo y extensible:

```json
{
  "format": "logicpad",
  "version": 1,
  "title": "Apuntes de lógica",
  "content": "Ley de De Morgan:\n\n¬(p ∧ q) ≡ ¬p ∨ ¬q",
  "created_at": "2026-09-25T10:00:00+00:00",
  "modified_at": "2026-09-25T10:05:00+00:00"
}
```

El contenido se guarda ya con los símbolos Unicode "visibles" (no la
sintaxis ASCII cruda), de forma que abrir el archivo más tarde muestra
exactamente lo que se veía al guardarlo.

---

## 9. Decisiones de diseño menores (no especificadas explícitamente)

Estas decisiones se han tomado siguiendo el criterio técnicamente más
razonable, tal y como pedía el encargo, y se documentan aquí de forma
resumida (los detalles están en los docstrings de cada módulo):

* Archivo `ast_nodes.py` en lugar de `ast.py` (ver sección 2).
* Asociatividad de cada operador (ver sección 5).
* Variables restringidas a minúsculas; `T`/`F` y `⊤`/`⊥` reservados
  para las constantes lógicas verdadero/falso.
* La conversión de escritura rápida ocurre de forma inmediata al
  completarse una secuencia, no al pulsar espacio/enter (ver sección 3).
* `≡` solo es válido en la posición más externa de una fórmula (no se
  anida ni se encadena), reflejando que representa una afirmación
  sobre dos expresiones y no un operador booleano normal como `↔`.
* Se añadió `logic/argument.py` (no estaba en la estructura de
  carpetas sugerida) para mantener la lógica de interpretación y
  validación de argumentos separada de la interfaz, igual que el
  resto de `logic/`.
* Los comandos de cuantificadores/conjuntos (`\forall`, `\in`...) son
  puramente de notación del Editor y NO se han añadido al lexer/parser
  de `logic/` (que sigue limitado a lógica proposicional): así se
  evita construir un parser matemático completo antes de tiempo (ver
  sección 4) y el motor de la Calculadora queda intacto.
* `\subset`/`\supset` necesitan un delimitador para convertirse, al
  ser prefijo de `\subseteq`/`\supseteq`; esto se detecta
  automáticamente comparando la tabla de comandos, no está
  "hardcodeado" (ver sección 4 y `utils/quick_entry.py`).
* «Conjuntos» es un **modo de primer nivel** (botón 4 de la pantalla de inicio),
  no una pestaña de la Calculadora: las pestañas de la Calculadora son de lógica
  proposicional y el modo necesita un diseño de dos zonas con todo el ancho.
* El cálculo de «Conjuntos» vive en `setcalc/` (sin Qt) y usa un símplex propio en
  lugar de SciPy: añadir una dependencia pesada para un problema de ≤ 64
  variables no compensa, y una propagación de cotas simple se demostró insuficiente
  con cardinales enormes (ver 4c). Se contrasta con fuerza bruta en los tests.
* El número de versión está en `utils/version.py` (`APP_VERSION`), que usa el
  diálogo «Acerca de». El proyecto de Android conserva su propio `versionName`.

---

## 10. Extensiones futuras (no implementadas en esta primera versión)

La arquitectura está pensada para poder añadir progresivamente, sin
reescribir lo existente:

* Deducción natural, modus ponens, modus tollens y otras reglas de
  inferencia (encajarían como un módulo nuevo dentro de `logic/`,
  reutilizando el AST existente).
* Demostraciones paso a paso guiadas por el usuario.
* Exportación de tablas de verdad (CSV, imagen...).
* Documentos con formato (negrita, títulos...).
* Modo oscuro.
* Personalización de los atajos de escritura rápida y de los comandos
  (la tabla ya está centralizada en `utils/symbols.py`, pensada para
  poder cargarse desde un archivo de configuración de usuario).
* Nuevas categorías matemáticas (relaciones, funciones, álgebra,
  cálculo...): basta con añadir símbolos nuevos a `utils/symbols.py`
  con su propia categoría; el selector, la ayuda y la conversión de
  escritura rápida los recogen automáticamente.
* Ejercicios interactivos de conjuntos; ampliar el motor `mathexpr/` con lo
  listado como pendiente en la sección 4b.
* Matemática Discreta: llevar los modos Funciones, Relaciones y el álgebra de
  conjuntos a Android; relaciones entre funciones con dominio ℚ; clausuras
  (reflexiva, simétrica, transitiva) y diagramas de Hasse.
* Modo «Conjuntos»: desigualdades en las condiciones (`|A ∩ B| ≥ 2`), más de 3
  conjuntos con otra representación visual, exportar el diagrama como imagen,
  arrastrar los círculos, y llevar el modo a Android.
* Autocompletado real de comandos mientras se escribe `\cu`, `\su`...
  (por ahora la conversión es solo de sustitución; el diseño de
  `utils/symbols.py` ya deja los datos listos — nombre, categoría — para
  cuando se aborde el autocompletado).
* Historial de expresiones recientes.
* Guardado de "proyectos" (varios documentos agrupados).
* Más conectores lógicos.
