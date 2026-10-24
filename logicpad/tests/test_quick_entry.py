"""
Tests de la conversión de escritura rápida: los atajos de puntuación
heredados de lógica (deben seguir funcionando exactamente igual) y los
nuevos comandos estilo LaTeX de cuantificadores y teoría de conjuntos,
incluida la desambiguación de comandos que son prefijo de otros
(``\\subset``/``\\subseteq``, ``\\supset``/``\\supseteq``).

Nota sobre los literales de cadena en este archivo: se usan cadenas
normales (no "raw") para los comandos, escribiendo la contrabarra como
``"\\\\"`` (por ejemplo ``"\\\\forall"``), para que no haya ninguna duda
sobre cuántas contrabarras contiene cada literal.
"""

from utils.quick_entry import (
    _IMMEDIATE_TABLE,
    LOGIC_CONVERTER,
    MATH_CONVERTER,
    SETS_CONVERTER,
    find_command_before_delimiter,
    find_completed_shortcut,
)

# --- Atajos de lógica heredados: deben seguir funcionando igual -------


def test_legacy_not():
    assert find_completed_shortcut("!") == ("!", "¬")


def test_legacy_and():
    assert find_completed_shortcut("p &&") == ("&&", "∧")


def test_legacy_or():
    assert find_completed_shortcut("p ||") == ("||", "∨")


def test_legacy_xor():
    assert find_completed_shortcut("p ^") == ("^", "⊕")


def test_legacy_implies():
    assert find_completed_shortcut("p ->") == ("->", "→")


def test_legacy_iff():
    assert find_completed_shortcut("p <->") == ("<->", "↔")


def test_legacy_equiv():
    assert find_completed_shortcut("p <=>") == ("<=>", "≡")


# --- "|" nunca debe convertirse a nada de conjuntos --------------------


def test_pipe_alone_never_converts():
    assert find_completed_shortcut("|") is None
    assert find_completed_shortcut("{x | x") is None


def test_pipe_not_a_trigger_in_any_table():
    assert all(seq != "|" for seq, _ in _IMMEDIATE_TABLE)


def test_pipe_still_usable_as_plain_character():
    # No debe haber ninguna conversión pendiente que ate "|" a un
    # símbolo de conjuntos: sigue disponible como "tal que".
    assert find_completed_shortcut("{x \u2208 \u2115 | x") is None


# --- Comandos estilo LaTeX: cuantificadores -----------------------------


def test_forall():
    assert find_completed_shortcut("\\forall") == ("\\forall", "\u2200")


def test_exists():
    assert find_completed_shortcut("\\exists") == ("\\exists", "\u2203")


# --- Comandos estilo LaTeX: conjuntos (no ambiguos) ---------------------


def test_in():
    assert find_completed_shortcut("\\in") == ("\\in", "\u2208")


def test_notin():
    assert find_completed_shortcut("\\notin") == ("\\notin", "\u2209")


def test_cup():
    assert find_completed_shortcut("\\cup") == ("\\cup", "\u222a")


def test_cap():
    assert find_completed_shortcut("\\cap") == ("\\cap", "\u2229")


def test_setminus():
    assert find_completed_shortcut("\\setminus") == ("\\setminus", "\u2216")


def test_emptyset():
    assert find_completed_shortcut("\\emptyset") == ("\\emptyset", "\u2205")


def test_times():
    assert find_completed_shortcut("\\times") == ("\\times", "\u00d7")


def test_subseteq_converts_immediately():
    # "\subseteq" no es prefijo de ningún otro comando, así que se
    # convierte en cuanto se completa, igual que los atajos heredados.
    assert find_completed_shortcut("\\subseteq") == ("\\subseteq", "\u2286")


def test_supseteq_converts_immediately():
    assert find_completed_shortcut("\\supseteq") == ("\\supseteq", "\u2287")


# --- \subset / \supset: ambiguos con \subseteq / \supseteq -------------


def test_subset_does_not_convert_immediately():
    # "\subset" SÍ es prefijo de "\subseteq": si se convirtiera solo,
    # sería imposible escribir "\subseteq".
    assert find_completed_shortcut("\\subset") is None


def test_supset_does_not_convert_immediately():
    assert find_completed_shortcut("\\supset") is None


def test_typing_subseteq_never_triggers_a_premature_conversion():
    partial_states = [
        "\\s", "\\su", "\\sub", "\\subs", "\\subse",
        "\\subset", "\\subsete", "\\subseteq",
    ]
    for state in partial_states[:-1]:
        assert find_completed_shortcut(state) is None, state
    assert find_completed_shortcut(partial_states[-1]) == ("\\subseteq", "\u2286")


def test_subset_converts_on_space_delimiter_and_gobbles_it():
    assert find_command_before_delimiter("\\subset ") == ("\\subset", "\u2282", True)


def test_subset_converts_on_symbol_delimiter_without_gobbling():
    assert find_command_before_delimiter("\\subset(") == ("\\subset", "\u2282", False)


def test_supset_converts_on_delimiter():
    assert find_command_before_delimiter("\\supset ") == ("\\supset", "\u2283", True)
    assert find_command_before_delimiter("\\supset)") == ("\\supset", "\u2283", False)


def test_subset_converts_before_a_new_command():
    # Una nueva contrabarra también termina el comando anterior sin
    # ambigüedad (igual que en LaTeX).
    result = find_command_before_delimiter("\\subset\\")
    assert result == ("\\subset", "\u2282", False)


# --- Casos sin coincidencia --------------------------------------------


def test_delimiter_helper_returns_none_without_a_command():
    assert find_command_before_delimiter("hola ") is None
    assert find_command_before_delimiter("p(") is None


def test_delimiter_helper_ignores_when_last_char_is_a_letter():
    # Si el último carácter todavía es una letra, el comando podría
    # seguir extendiéndose: no debe dispararse nada.
    assert find_command_before_delimiter("\\subsetA") is None


def test_unknown_command_does_not_convert():
    assert find_completed_shortcut("\\unknown") is None
    assert find_command_before_delimiter("\\unknown ") is None


# --- Salvaguarda: ningún atajo de puntuación de NINGÚN conversor debe
#     ser prefijo de otro del MISMO conversor (si lo fuera, la
#     conversión inmediata dispararía antes de tiempo, como pasaba con
#     "!" siendo prefijo de "!="; ver utils/quick_entry.py). -----------


def test_math_converter_does_not_convert_caret_to_xor():
    # En el campo de expresiones matemáticas, "^" debe quedarse como
    # "^" (potencia), NO convertirse a "⊕" (eso solo pasa en el
    # conversor de lógica).
    assert MATH_CONVERTER.find_completed_shortcut("x^") is None
    assert LOGIC_CONVERTER.find_completed_shortcut("p^") == ("^", "\u2295")


def test_math_converter_comparison_shortcuts():
    assert MATH_CONVERTER.find_completed_shortcut("x <=") == ("<=", "\u2264")
    assert MATH_CONVERTER.find_completed_shortcut("x >=") == (">=", "\u2265")
    assert MATH_CONVERTER.find_completed_shortcut("x <>") == ("<>", "\u2260")


def test_math_converter_keeps_safe_legacy_shortcuts():
    assert MATH_CONVERTER.find_completed_shortcut("!") == ("!", "\u00ac")
    assert MATH_CONVERTER.find_completed_shortcut("p &&") == ("&&", "\u2227")
    assert MATH_CONVERTER.find_completed_shortcut("p ||") == ("||", "\u2228")
    assert MATH_CONVERTER.find_completed_shortcut("p ->") == ("->", "\u2192")
    assert MATH_CONVERTER.find_completed_shortcut("p <->") == ("<->", "\u2194")


def test_math_converter_does_not_have_equiv_shortcut():
    # "<=>" (equivalencia de expresiones) no pertenece a la gramática
    # de expresiones matemáticas.
    assert MATH_CONVERTER.find_completed_shortcut("p <=>") != ("<=>", "\u2261")


def test_math_converter_shares_latex_commands_with_logic_converter():
    assert MATH_CONVERTER.find_completed_shortcut("\\forall") == ("\\forall", "\u2200")
    assert MATH_CONVERTER.find_completed_shortcut("\\to") == ("\\to", "\u2192")
    assert MATH_CONVERTER.find_completed_shortcut("\\mapsto") == ("\\mapsto", "\u21a6")
    assert MATH_CONVERTER.find_completed_shortcut("\\le") == ("\\le", "\u2264")
    assert MATH_CONVERTER.find_completed_shortcut("\\ge") == ("\\ge", "\u2265")


def test_no_prefix_conflicts_within_any_converter():
    for converter in (LOGIC_CONVERTER, MATH_CONVERTER, SETS_CONVERTER):
        sequences = [seq for seq, _ in converter.immediate_table]
        for seq in sequences:
            others = [other for other in sequences if other != seq]
            assert not any(other.startswith(seq) for other in others), (
                f"'{seq}' es prefijo de otra secuencia en el mismo conversor"
            )



def test_set_operation_commands_triangle_and_complement():
    assert LOGIC_CONVERTER.find_completed_shortcut("A \\triangle") == ("\\triangle", "\u25b3")
    assert LOGIC_CONVERTER.find_completed_shortcut("A \\complement") == ("\\complement", "\u1d9c")


def test_sets_converter_only_converts_commands_never_punctuation():
    assert SETS_CONVERTER.find_completed_shortcut("A \\cup") == ("\\cup", "\u222a")
    for text in ("!", "p ^", "p &&", "p ||", "p ->", "x <="):
        assert SETS_CONVERTER.find_completed_shortcut(text) is None, text
