import pytest

from app.validators import (
    escapar_like,
    formatar_preco_input,
    parse_inteiro,
    parse_preco,
    validar_categoria,
    validar_curso,
    validar_produto,
    validar_servico,
)


@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("55", 5500),
        ("55,00", 5500),
        ("55,5", 5550),
        ("55.50", 5550),
        ("0,99", 99),
        ("R$ 55,00", 5500),
        ("R$55", 5500),
        ("1.234,56", 123456),
        ("1.234", 123400),  # ponto + 3 dígitos = milhar
        ("999.999,99", 99999999),
        ("  12,34  ", 1234),
        ("1 234,50", 123450),  # espaço invisível colado do Word/WhatsApp
        ("1000000", 100000000),
        ("0", 0),
    ],
)
def test_parse_preco_aceita(texto, esperado):
    assert parse_preco(texto) == esperado


@pytest.mark.parametrize(
    "texto",
    [None, "", "   ", "abc", "-5", "5,555", "5,5,5", "1.2.3", "R$", "1000000,01", "1.234.567,89", "99999999999", "5e2", "12 34,5x"],
)
def test_parse_preco_recusa(texto):
    assert parse_preco(texto) is None


@pytest.mark.parametrize("centavos, esperado", [(5500, "55,00"), (5, "0,05"), (123456, "1234,56"), (None, "")])
def test_formatar_preco_input(centavos, esperado):
    assert formatar_preco_input(centavos) == esperado


def test_preco_formatado_volta_igual():
    for centavos in (1, 99, 5500, 123456, 100000000):
        assert parse_preco(formatar_preco_input(centavos)) == centavos


@pytest.mark.parametrize("texto, esperado", [("0", 0), ("12", 12), (" 7 ", 7), ("100000", 100000)])
def test_parse_inteiro_aceita(texto, esperado):
    assert parse_inteiro(texto) == esperado


@pytest.mark.parametrize("texto", [None, "", "-1", "1,5", "1.5", "abc", "100001", "99999999999"])
def test_parse_inteiro_recusa(texto):
    assert parse_inteiro(texto) is None


def test_escapar_like():
    assert escapar_like("100%_a\\b") == "100\\%\\_a\\\\b"


FORM_PRODUTO = {
    "nome": "Caneca azul", "categoria_id": "3", "preco": "55,00", "estoque": "4",
    "descricao": "Feita à mão", "ativo": "on",
}


def test_validar_produto_ok():
    dados, erros = validar_produto(FORM_PRODUTO)
    assert erros == []
    assert dados["preco_centavos"] == 5500
    assert dados["estoque"] == 4
    assert dados["categoria_id_int"] == 3
    assert dados["ativo"] is True


def test_validar_produto_sem_checkbox_fica_inativo():
    form = {k: v for k, v in FORM_PRODUTO.items() if k != "ativo"}
    dados, erros = validar_produto(form)
    assert erros == []
    assert dados["ativo"] is False


@pytest.mark.parametrize(
    "campo, valor, trecho_do_erro",
    [
        ("nome", "   ", "nome do produto"),
        ("nome", "x" * 151, "150"),
        ("preco", "abc", "preço válido"),
        ("preco", "0", "maior que zero"),
        ("preco", "", "preço válido"),
        ("estoque", "", "estoque"),
        ("estoque", "-2", "estoque"),
        ("estoque", "2,5", "estoque"),
        ("categoria_id", "", "categoria"),
        ("categoria_id", "abc", "categoria"),
        ("descricao", "x" * 5001, "5000"),
    ],
)
def test_validar_produto_erros(campo, valor, trecho_do_erro):
    dados, erros = validar_produto({**FORM_PRODUTO, campo: valor})
    assert len(erros) == 1
    assert trecho_do_erro in erros[0]


def test_validar_produto_guarda_o_que_foi_digitado_para_reexibir():
    dados, erros = validar_produto({**FORM_PRODUTO, "preco": "abc"})
    assert dados["preco_texto"] == "abc"
    assert dados["preco_centavos"] is None
    assert dados["nome"] == "Caneca azul"


def test_validar_categoria():
    dados, erros = validar_categoria({"nome": "  Pratos ", "ativa": "on"})
    assert (dados["nome"], dados["ativa"], erros) == ("Pratos", True, [])
    assert validar_categoria({"nome": ""})[1]
    assert validar_categoria({"nome": "x" * 81})[1]
    assert validar_categoria({"nome": "ok"})[0]["ativa"] is False


def test_validar_curso_valor_opcional():
    dados, erros = validar_curso({"titulo": "Torno", "valor": ""})
    assert erros == [] and dados["valor_centavos"] is None

    dados, erros = validar_curso({"titulo": "Torno", "valor": "250,00", "duracao": "4 encontros", "ativo": "on"})
    assert erros == [] and dados["valor_centavos"] == 25000 and dados["ativo"] is True

    assert validar_curso({"titulo": "Torno", "valor": "caro"})[1]
    assert validar_curso({"titulo": ""})[1]
    assert validar_curso({"titulo": "T", "duracao": "x" * 81})[1]


def test_validar_servico():
    dados, erros = validar_servico({"titulo": "Queima", "descricao": "Queima de peças", "ativo": "on"})
    assert erros == [] and dados["ativo"] is True
    assert validar_servico({"titulo": " "})[1]
