import pytest

from app.utils import brl, destino_seguro, slugify


@pytest.mark.parametrize(
    "centavos, esperado",
    [(0, "R$ 0,00"), (5, "R$ 0,05"), (5500, "R$ 55,00"), (123456, "R$ 1.234,56"),
     (100000000, "R$ 1.000.000,00"), (None, "")],
)
def test_brl(centavos, esperado):
    assert brl(centavos) == esperado


@pytest.mark.parametrize(
    "texto, esperado",
    [("Caneca Azul Grande", "caneca-azul-grande"), ("Peça de Cerâmica", "peca-de-ceramica"),
     ("  --Vaso  /  Mesa!! ", "vaso-mesa")],
)
def test_slugify(texto, esperado):
    assert slugify(texto) == esperado


@pytest.mark.parametrize("destino", ["/conta", "/loja/?categoria=canecas", "/admin/"])
def test_destino_seguro_aceita_caminhos_internos(destino):
    assert destino_seguro(destino)


@pytest.mark.parametrize(
    "destino", ["", None, "//evil.com", "https://evil.com", "javascript:alert(1)", "/\\evil.com", "evil.com"]
)
def test_destino_seguro_recusa_o_resto(destino):
    assert not destino_seguro(destino)
