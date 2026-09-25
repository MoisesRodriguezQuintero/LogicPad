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
│   └── widgets.py            # Widgets Qt reutilizables (LogicLineEdit)
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
├── models/
│   └── document.py           # Modelo de documento (.logicpad, JSON)
│
├── utils/
│   ├── quick_entry.py         # Lógica pura de conversión ASCII -> Unicode
│   └── shortcuts.py           # Tabla de atajos de escritura rápida
│
└── tests/
    ├── test_lexer.py
    ├── test_parser.py
    ├── test_evaluator.py
    ├── test_truth_table.py
    ├── test_equivalence.py
    ├── test_simplifier.py
    └── test_argument.py
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

## 4. Precedencia y asociatividad de operadores

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

## 5. Los tres modos de trabajo

### 5.1. Editor

Editor de texto sencillo para apuntes que mezclan texto normal y
expresiones lógicas, con conversión automática de escritura rápida.
Permite crear, abrir y guardar documentos en el formato propio
`.logicpad` (JSON internamente), además de las operaciones básicas de
edición (deshacer/rehacer, copiar/pegar, seleccionar).

### 5.2. Calculadora lógica

Tres pestañas:

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

### 5.3. LogicPad (modo avanzado)

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

## 6. Simplificador: reglas implementadas

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

## 7. Formato de archivo `.logicpad`

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

## 8. Decisiones de diseño menores (no especificadas explícitamente)

Estas decisiones se han tomado siguiendo el criterio técnicamente más
razonable, tal y como pedía el encargo, y se documentan aquí de forma
resumida (los detalles están en los docstrings de cada módulo):

* Archivo `ast_nodes.py` en lugar de `ast.py` (ver sección 2).
* Asociatividad de cada operador (ver sección 4).
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

---

## 9. Extensiones futuras (no implementadas en esta primera versión)

La arquitectura está pensada para poder añadir progresivamente, sin
reescribir lo existente:

* Deducción natural, modus ponens, modus tollens y otras reglas de
  inferencia (encajarían como un módulo nuevo dentro de `logic/`,
  reutilizando el AST existente).
* Demostraciones paso a paso guiadas por el usuario.
* Exportación de tablas de verdad (CSV, imagen...).
* Documentos con formato (negrita, títulos...).
* Modo oscuro.
* Personalización de los atajos de escritura rápida (la tabla ya está
  centralizada en `utils/shortcuts.py`, pensada para poder cargarse
  desde un archivo de configuración de usuario).
* Historial de expresiones recientes.
* Guardado de "proyectos" (varios documentos agrupados).
* Más conectores lógicos.
