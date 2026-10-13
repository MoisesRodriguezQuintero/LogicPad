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
selección de modo (Editor / Calculadora lógica / LogicPad).

### 1.4. Ejecutar los tests

El motor lógico (`logic/`) tiene una batería de tests independiente de
la interfaz gráfica:

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
├── models/
│   └── document.py           # Modelo de documento (.logicpad, JSON)
│
├── utils/
│   ├── quick_entry.py         # Lógica pura de conversión de escritura rápida
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
    └── test_mathexpr_*.py     # Lexer, parser, evaluador y sesión de mathexpr
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

## 6. Los tres modos de trabajo

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
* Diagramas de Venn y ejercicios interactivos de conjuntos; ampliar el
  motor `mathexpr/` con lo listado como pendiente en la sección 4b.
* Autocompletado real de comandos mientras se escribe `\cu`, `\su`...
  (por ahora la conversión es solo de sustitución; el diseño de
  `utils/symbols.py` ya deja los datos listos — nombre, categoría — para
  cuando se aborde el autocompletado).
* Historial de expresiones recientes.
* Guardado de "proyectos" (varios documentos agrupados).
* Más conectores lógicos.
