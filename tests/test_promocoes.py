"""Promoções: um único lugar calcula preço (app/services/precos.py) e todo o site usa ele.

Vitrine, peça, cursos, carrinho e checkout mostram/cobram o mesmo valor.
"""
from datetime import datetime, timedelta, timezone

import pytest
from werkzeug.datastructures import MultiDict

from app.extensions import db
from app.models import Course, Pedido, Product, Promocao
from app.services import mercadopago
from app.services.precos import preco_curso, preco_produto
from app.validators import formatar_data_hora_input, parse_data_hora, validar_promocao

AGORA = datetime.now(timezone.utc)


def prod(slug="caneca-azul"):
    return Product.query.filter_by(slug=slug).first()


def criar_promocao(produtos=(), cursos=(), tipo="percentual", valor=20, inicio=-1, fim=24, ativa=True, nome="Semana"):
    """inicio/fim em horas a partir de agora."""
    promo = Promocao(nome=nome, tipo=tipo, ativa=ativa,
                     percentual=valor if tipo == "percentual" else None,
                     valor_centavos=valor if tipo == "valor" else None,
                     inicio=AGORA + timedelta(hours=inicio), fim=AGORA + timedelta(hours=fim))
    promo.produtos.extend(produtos)
    promo.cursos.extend(cursos)
    db.session.add(promo)
    db.session.commit()
    return promo


@pytest.fixture()
def curso(app):
    c = Course(titulo="Introdução ao torno", slug="introducao-ao-torno", valor_centavos=25000, duracao="4 encontros")
    db.session.add(c)
    db.session.commit()
    return c


# ---------- Cálculo ----------

def test_percentual(catalogo):
    criar_promocao([prod()], valor=20)
    p = preco_produto(prod())
    assert (p.original, p.final) == (5500, 4400) and p.selo == "−20%"


def test_valor_fixo(catalogo):
    criar_promocao([prod()], tipo="valor", valor=1000)
    p = preco_produto(prod())
    assert p.final == 4500 and p.selo == "−R$ 10,00"


def test_desconto_percentual_arredonda_pra_baixo(catalogo):
    prod().preco_centavos = 5555
    criar_promocao([prod()], valor=33)  # 33% de 55,55 = 18,3315 -> desconto de 18,33
    assert preco_produto(prod()).final == 3722


def test_duas_promocoes_vale_a_de_menor_preco(catalogo):
    criar_promocao([prod()], valor=10, nome="Pequena")
    criar_promocao([prod()], tipo="valor", valor=2000, nome="Grande")
    p = preco_produto(prod())
    assert p.final == 3500 and p.promocao.nome == "Grande"


@pytest.mark.parametrize("inicio, fim, ativa", [(2, 24, True), (-24, -1, True), (-1, 24, False)])
def test_fora_do_periodo_ou_desativada_nao_vale(catalogo, inicio, fim, ativa):
    criar_promocao([prod()], inicio=inicio, fim=fim, ativa=ativa)
    p = preco_produto(prod())
    assert p.final == 5500 and p.promocao is None


def test_fim_nao_entra_no_periodo(catalogo):
    promo = criar_promocao([prod()])
    assert preco_produto(prod(), agora=promo.fim).promocao is None
    assert preco_produto(prod(), agora=promo.fim - timedelta(seconds=1)).promocao is not None


def test_desconto_que_zeraria_o_preco_e_ignorado(catalogo):
    criar_promocao([prod()], tipo="valor", valor=5500)  # gravado direto, sem passar pela validação
    assert preco_produto(prod()).final == 5500


def test_curso_com_e_sem_valor(catalogo, curso):
    sob_consulta = Course(titulo="Modelagem", slug="modelagem", valor_centavos=None)
    db.session.add(sob_consulta)
    criar_promocao(cursos=[curso, sob_consulta], valor=10)
    assert preco_curso(curso).final == 22500
    p = preco_curso(sob_consulta)
    assert p.final is None and p.promocao is None


def test_situacao_no_painel(catalogo):
    assert criar_promocao([prod()], inicio=2).situacao() == "agendada"
    assert criar_promocao([prod()]).situacao() == "valendo"
    assert criar_promocao([prod()], inicio=-24, fim=-1).situacao() == "encerrada"
    assert criar_promocao([prod()], ativa=False).situacao() == "desativada"


def test_data_do_painel_e_no_horario_de_brasilia():
    utc = parse_data_hora("2026-11-20T23:30")
    assert utc == datetime(2026, 11, 21, 2, 30, tzinfo=timezone.utc)
    assert formatar_data_hora_input(utc) == "2026-11-20T23:30"
    assert parse_data_hora("20/11/2026") is None and parse_data_hora("") is None


# ---------- Validação ----------

PRECOS_PRODUTOS = {1: 5500, 2: 7200}
PRECOS_CURSOS = {7: 25000, 8: None}


def form(**campos):
    base = {"nome": "Black Friday", "tipo": "percentual", "percentual": "20", "valor": "",
            "inicio": "2026-11-20T00:00", "fim": "2026-11-30T23:59", "ativa": "on"}
    base.update({k: v for k, v in campos.items() if k not in ("produtos", "cursos")})
    md = MultiDict(base)
    for pid in campos.get("produtos", ["1"]):
        md.add("produtos", pid)
    for cid in campos.get("cursos", []):
        md.add("cursos", cid)
    return md


def test_validar_promocao_percentual_ok():
    dados, erros = validar_promocao(form(cursos=["7"]), PRECOS_PRODUTOS, PRECOS_CURSOS)
    assert erros == []
    assert dados["percentual"] == 20 and dados["valor_centavos"] is None
    assert dados["produto_ids"] == [1] and dados["curso_ids"] == [7] and dados["ativa"] is True


def test_validar_promocao_valor_fixo_ok():
    dados, erros = validar_promocao(form(tipo="valor", valor="10,00", produtos=["1", "2"]), PRECOS_PRODUTOS, PRECOS_CURSOS)
    assert erros == [] and dados["valor_centavos"] == 1000 and dados["percentual"] is None


@pytest.mark.parametrize("campos", [
    {"nome": ""}, {"nome": "x" * 81}, {"tipo": "brinde"},
    {"percentual": "0"}, {"percentual": "91"}, {"percentual": "abc"},
    {"tipo": "valor", "valor": "0"}, {"tipo": "valor", "valor": "55,00"},  # igual ao menor preço marcado
    {"fim": "2026-11-19T00:00"}, {"inicio": "amanhã"},
    {"produtos": [], "cursos": []}, {"produtos": ["999"]}, {"produtos": [], "cursos": ["8"]},
])
def test_validar_promocao_recusa(campos):
    _, erros = validar_promocao(form(**campos), PRECOS_PRODUTOS, PRECOS_CURSOS)
    assert erros


# ---------- Vitrine ----------

def test_loja_mostra_preco_riscado_e_selo(client, catalogo):
    Product_outro = Product(nome="Prato raso", slug="prato-raso", preco_centavos=7200, estoque=2,
                            categoria=prod().categoria)
    db.session.add(Product_outro)
    db.session.commit()
    criar_promocao([prod()], valor=20)
    html = client.get("/loja/").get_data(as_text=True)
    assert '<s class="preco__antigo">R$ 55,00</s>' in html and "R$ 44,00" in html
    assert html.count("selo--promo") == 1 and "−20%" in html
    assert "R$ 72,00" in html


def test_peca_mostra_preco_riscado_e_validade(client_cliente, catalogo):
    promo = criar_promocao([prod()], valor=20)
    html = client_cliente.get("/loja/caneca-azul").get_data(as_text=True)
    assert "R$ 44,00" in html and '<s class="preco__antigo">R$ 55,00</s>' in html
    assert "Promoção até" in html


def test_cursos_mostram_preco_riscado(client, catalogo, curso):
    criar_promocao(cursos=[curso], valor=10)
    html = client.get("/cursos").get_data(as_text=True)
    assert '<s class="preco__antigo">R$ 250,00</s>' in html and "R$ 225,00" in html


def test_promocao_agendada_nao_aparece(client, catalogo):
    criar_promocao([prod()], inicio=2)
    html = client.get("/loja/").get_data(as_text=True)
    assert "preco__antigo" not in html and "selo--promo" not in html


# ---------- Carrinho e checkout ----------

class MPFalso:
    def __init__(self):
        self.corpos = []

    def __call__(self, metodo, caminho, corpo=None, idempotencia=None):
        self.corpos.append(corpo)
        return {"id": "pref-1", "init_point": "https://mp.exemplo.test/x"}


def test_carrinho_cobra_o_preco_da_promocao(client_cliente, catalogo):
    criar_promocao([prod()], valor=20)
    client_cliente.post(f"/carrinho/adicionar/{prod().id}", data={"quantidade": "2"})
    html = client_cliente.get("/carrinho/").get_data(as_text=True)
    assert "R$ 88,00" in html and '<s class="preco__antigo">R$ 55,00</s>' in html


def test_pedido_guarda_preco_com_desconto_e_original(client_cliente, catalogo, monkeypatch):
    falso = MPFalso()
    monkeypatch.setattr(mercadopago, "_requisicao", falso)
    criar_promocao([prod()], valor=20)
    client_cliente.post(f"/carrinho/adicionar/{prod().id}", data={"quantidade": "2"})
    client_cliente.get("/checkout/")
    with client_cliente.session_transaction() as s:
        token = s["checkout_token"]
    client_cliente.post("/checkout/confirmar", data={"token": token, "entrega": "retirada"})
    item = Pedido.query.one().itens[0]
    assert item.preco_unitario_centavos == 4400 and item.preco_original_centavos == 5500
    assert Pedido.query.one().total_centavos == 8800
    assert falso.corpos[0]["items"][0]["unit_price"] == 44.0
    html = client_cliente.get(f"/conta/pedidos/{Pedido.query.one().id}").get_data(as_text=True)
    assert '<s class="preco__antigo">R$ 55,00</s>' in html


def test_promocao_que_acaba_no_meio_da_compra_nao_cria_pedido(client_cliente, catalogo, monkeypatch):
    monkeypatch.setattr(mercadopago, "_requisicao", MPFalso())
    promo = criar_promocao([prod()], valor=20)
    client_cliente.post(f"/carrinho/adicionar/{prod().id}", data={"quantidade": "1"})
    client_cliente.get("/checkout/")  # viu R$ 44,00
    with client_cliente.session_transaction() as s:
        token = s["checkout_token"]
    promo.ativa = False  # a Julia encerrou a promoção
    db.session.commit()
    r = client_cliente.post("/checkout/confirmar", data={"token": token, "entrega": "retirada"}, follow_redirects=True)
    assert Pedido.query.count() == 0
    assert "O preço mudou" in r.get_data(as_text=True)


# ---------- Painel ----------

def test_painel_de_promocoes_exige_login(client):
    assert client.get("/admin/promocoes").status_code == 302


def test_cliente_comum_nao_entra_no_painel_de_promocoes(client_cliente):
    assert client_cliente.get("/admin/promocoes").status_code == 403
    assert client_cliente.post("/admin/promocoes/nova", data={}).status_code == 403


def dados_do_form(**extra):
    dados = {"nome": "Semana das canecas", "tipo": "percentual", "percentual": "15", "valor": "",
             "inicio": formatar_data_hora_input(AGORA - timedelta(hours=1)),
             "fim": formatar_data_hora_input(AGORA + timedelta(days=7)), "ativa": "on",
             "produtos": [str(prod().id)]}
    dados.update(extra)
    return dados


def test_admin_cria_promocao(client_admin, catalogo):
    r = client_admin.post("/admin/promocoes/nova", data=dados_do_form())
    assert r.status_code == 302 and r.headers["Location"] == "/admin/promocoes"
    promo = Promocao.query.one()
    assert promo.percentual == 15 and promo.produtos == [prod()]
    assert "Valendo" in client_admin.get("/admin/promocoes").get_data(as_text=True)
    assert preco_produto(prod()).final == 4675


def test_admin_promocao_invalida_nao_salva(client_admin, catalogo):
    html = client_admin.post("/admin/promocoes/nova", data=dados_do_form(percentual="95")).get_data(as_text=True)
    assert Promocao.query.count() == 0 and "aviso--erro" in html


def test_admin_edita_alterna_e_exclui(client_admin, catalogo, curso):
    promo = criar_promocao([prod()], valor=20)
    client_admin.post(f"/admin/promocoes/{promo.id}/editar",
                      data=dados_do_form(percentual="30", produtos=[], cursos=[str(curso.id)]))
    db.session.refresh(promo)
    assert promo.percentual == 30 and promo.produtos == [] and promo.cursos == [curso]
    client_admin.post(f"/admin/promocoes/{promo.id}/alternar")
    assert db.session.get(Promocao, promo.id).ativa is False
    client_admin.post(f"/admin/promocoes/{promo.id}/excluir")
    assert Promocao.query.count() == 0


def test_excluir_produto_em_promocao_nao_quebra(client_admin, catalogo):
    promo = criar_promocao([prod()], valor=20)
    client_admin.post(f"/admin/produtos/{prod().id}/excluir")
    assert prod() is None and db.session.get(Promocao, promo.id).produtos == []
