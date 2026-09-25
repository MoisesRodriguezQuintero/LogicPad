import pytest

from logic.argument import ArgumentParseError, check_validity, parse_argument


def test_parse_with_dash_separator():
    text = "p -> q\nq -> r\n------\np -> r"
    arg = parse_argument(text)
    assert len(arg.premises) == 2
    assert arg.conclusion_text == "p -> r"


def test_parse_with_turnstile_symbol():
    text = "p -> q\nq -> r\n∴ p -> r"
    arg = parse_argument(text)
    assert len(arg.premises) == 2


def test_valid_hypothetical_syllogism():
    arg = parse_argument("p -> q\nq -> r\n------\np -> r")
    result = check_validity(arg)
    assert result.is_valid is True
    assert result.counterexample is None


def test_invalid_argument_has_counterexample():
    arg = parse_argument("p -> q\n------\nq -> p")
    result = check_validity(arg)
    assert result.is_valid is False
    assert result.counterexample is not None


def test_modus_ponens_is_valid():
    arg = parse_argument("p -> q\np\n------\nq")
    result = check_validity(arg)
    assert result.is_valid is True


def test_too_few_lines_raises():
    with pytest.raises(ArgumentParseError):
        parse_argument("p -> q")


def test_invalid_premise_syntax_raises():
    with pytest.raises(ArgumentParseError):
        parse_argument("p &&\n------\nq")
