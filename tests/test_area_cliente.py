"""Área do cliente: dados, endereço, favoritos e histórico de pedidos.

Regra de ouro (skill saas-flask-seguranca, seção 1): cliente A nunca vê dado do cliente B.
Dado de outra pessoa pedido pela URL responde 404 (não 403: não revela que existe).

Um cliente de teste por função: o conftest mantém o app_context aberto e o Flask-Login
guarda o usuário em `g`. Os dados do "cliente B" são criados direto no banco.
"""
from urllib.parse import parse_qs, urlparse

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Endereco, Favorito, ItemPedido, Pedido, Product, User
from app.validators import validar_endereco, validar_telefone

SENHA = "senha-segura-123"
ENDERECO_OK = {"cep": "12246-000", "logradouro": "Rua Espanha", "numero": "532",
               "complemento": "Casa 2", "bairro": "Jardim das Nações", "cidade": "Taubaté", "uf": "sp"}


def prod(slug="caneca-azul"):
    return Product.query.filter_by(slug=slug).first()


def eu():
    return User.query.filter_by(email="cliente@exemplo.com").first()


def outra_pessoa():
    """Cliente B, criado direto no banco, com endereço, favorito e pedido."""
    b = User(nome="Bruno B", email="bruno@exemplo.com")
    b.set_password(SENHA)
    db.session.add(b)
    db.session.flush()
    db.session.add(Endereco(user_id=b.id, cep="01001000", logradouro="Praça da Sé do Bruno",
                            numero="1", bairro="Sé", cidade="São Paulo", uf="SP"))
    db.session.add(Favorito(user_id=b.id, produto_id=prod().id))
    pedido = criar_pedido(b, nome_item="Caneca do Bruno")
    db.session.commit()
    return b, pedido


def criar_pedido(usuario, nome_item="Caneca azul", preco=5500, quantidade=2, status="pago"):
    pedido = Pedido(user_id=usuario.id, status=status, subtotal_centavos=preco * quantidade,
                    frete_centavos=0, total_centavos=preco * quantidade,
                    entrega_cep="12246000", entrega_logradouro="Rua Espanha", entrega_numero="532",
                    entrega_bairro="Jardim das Nações", entrega_cidade="Taubaté", entrega_uf="SP")
    pedido.itens.append(ItemPedido(produto_id=prod().id, nome_produto=nome_item,
                                   preco_unitario_centavos=preco, quantidade=quantidade))
    db.session.add(pedido)
    db.session.commit()
    return pedido


def destino_do_login(resposta):
    assert resposta.status_code == 302
    url = urlparse(resposta.headers["Location"])
    assert url.path == "/entrar"
    return parse_qs(url.query).get("next", [None])[0]


# ---------- Validações puras ----------

def test_validar_endereco_normaliza():
    dados, erros = validar_endereco(ENDERECO_OK)
    assert erros == []
    assert dados["cep"] == "12246000" and dados["uf"] == "SP"


@pytest.mark.parametrize("campo, valor", [("cep", "1224"), ("cep", "abcde-fgh"), ("uf", "XX"),
                                          ("logradouro", ""), ("numero", ""), ("bairro", ""),
                                          ("cidade", ""), ("logradouro", "x" * 151)])
def test_validar_endereco_recusa(campo, valor):
    _, erros = validar_endereco({**ENDERECO_OK, campo: valor})
    assert erros


@pytest.mark.parametrize("texto, esperado", [("(12) 99139-9090", "12991399090"), ("12 3456-7890", "1234567890"),
                                             ("", ""), ("123", None), ("(12) 99139-90901", None)])
def test_validar_telefone(texto, esperado):
    assert validar_telefone(texto) == esperado


# ---------- Tudo em /conta/* exige login ----------

@pytest.mark.parametrize("rota", ["/conta/dados", "/conta/endereco", "/conta/favoritos",
                                  "/conta/pedidos", "/conta/pedidos/1"])
def test_area_do_cliente_exige_login(client, rota):
    assert destino_do_login(client.get(rota)) == rota


def test_favoritar_sem_login_volta_pra_peca(client, catalogo):
    r = client.post(f"/conta/favoritos/{prod().id}", data={"acao": "adicionar"})
    assert destino_do_login(r) == "/loja/caneca-azul"
    assert Favorito.query.count() == 0


# ---------- Dados pessoais ----------

def test_atualiza_nome_e_telefone(client_cliente):
    r = client_cliente.post("/conta/dados", data={"nome": "Ana Clara", "telefone": "(12) 99139-9090",
                                                  "email": "cliente@exemplo.com"})
    assert r.status_code == 302
    assert eu().nome == "Ana Clara" and eu().telefone == "12991399090"


@pytest.mark.parametrize("dados", [{"nome": "", "telefone": ""}, {"nome": "Ana", "telefone": "123"}])
def test_dados_invalidos_nao_salvam(client_cliente, dados):
    html = client_cliente.post("/conta/dados", data={**dados, "email": "cliente@exemplo.com"}).get_data(as_text=True)
    assert "aviso--erro" in html
    assert eu().nome == "Pessoa Teste"


def test_trocar_email_exige_senha_atual(client_cliente):
    client_cliente.post("/conta/dados", data={"nome": "Ana", "email": "nova@exemplo.com", "senha_atual": "errada"})
    assert eu() is not None  # e-mail continua o antigo
    client_cliente.post("/conta/dados", data={"nome": "Ana", "email": "nova@exemplo.com", "senha_atual": SENHA})
    assert User.query.filter_by(email="nova@exemplo.com").first() is not None


def test_nao_troca_para_email_de_outra_conta(client_cliente, criar_usuario):
    criar_usuario(email="ocupado@exemplo.com")
    client_cliente.post("/conta/dados", data={"nome": "Ana", "email": "ocupado@exemplo.com", "senha_atual": SENHA})
    assert eu() is not None


@pytest.mark.parametrize("dados", [
    {"senha_atual": "errada", "nova_senha": "outra-senha-123", "confirmacao": "outra-senha-123"},
    {"senha_atual": SENHA, "nova_senha": "curta", "confirmacao": "curta"},
    {"senha_atual": SENHA, "nova_senha": "outra-senha-123", "confirmacao": "diferente-123"},
])
def test_troca_de_senha_invalida(client_cliente, dados):
    client_cliente.post("/conta/senha", data=dados)
    assert eu().check_password(SENHA)


def test_troca_de_senha(client_cliente):
    client_cliente.post("/conta/senha", data={"senha_atual": SENHA, "nova_senha": "outra-senha-123",
                                              "confirmacao": "outra-senha-123"})
    assert eu().check_password("outra-senha-123")


# ---------- Endereço (um por cliente, sem ID na URL) ----------

def test_cria_e_edita_o_endereco(client_cliente):
    client_cliente.post("/conta/endereco", data=ENDERECO_OK)
    client_cliente.post("/conta/endereco", data={**ENDERECO_OK, "numero": "600"})
    enderecos = Endereco.query.filter_by(user_id=eu().id).all()
    assert len(enderecos) == 1 and enderecos[0].numero == "600"
    assert "12246-000" in client_cliente.get("/conta/endereco").get_data(as_text=True)


def test_endereco_invalido_nao_salva(client_cliente):
    html = client_cliente.post("/conta/endereco", data={**ENDERECO_OK, "uf": "XX"}).get_data(as_text=True)
    assert "aviso--erro" in html and Endereco.query.count() == 0


# ---------- Favoritos ----------

def test_favoritar_e_desfavoritar(client_cliente, catalogo):
    pid = prod().id
    client_cliente.post(f"/conta/favoritos/{pid}", data={"acao": "adicionar"})
    client_cliente.post(f"/conta/favoritos/{pid}", data={"acao": "adicionar"})  # 2 toques: continua 1
    assert Favorito.query.filter_by(user_id=eu().id).count() == 1
    assert "Caneca azul" in client_cliente.get("/conta/favoritos").get_data(as_text=True)
    client_cliente.post(f"/conta/favoritos/{pid}", data={"acao": "remover"})
    assert Favorito.query.count() == 0


def test_favoritar_volta_pra_pagina_de_origem(client_cliente, catalogo):
    r = client_cliente.post(f"/conta/favoritos/{prod().id}", data={"acao": "adicionar", "voltar": "/loja/?categoria=canecas"})
    assert r.headers["Location"] == "/loja/?categoria=canecas"
    r = client_cliente.post(f"/conta/favoritos/{prod().id}", data={"acao": "remover", "voltar": "https://evil.com/"})
    assert r.headers["Location"] == "/loja/caneca-azul"


def test_nao_favorita_produto_inativo_ou_inexistente(client_cliente, catalogo):
    assert client_cliente.post(f"/conta/favoritos/{prod('caneca-oculta').id}", data={"acao": "adicionar"}).status_code == 404
    assert client_cliente.post("/conta/favoritos/99999", data={"acao": "adicionar"}).status_code == 404


def test_coracao_no_cartao_e_na_peca_mostra_o_estado(client_cliente, catalogo):
    pid = prod().id
    assert f'action="/conta/favoritos/{pid}"' in client_cliente.get("/loja/").get_data(as_text=True)
    client_cliente.post(f"/conta/favoritos/{pid}", data={"acao": "adicionar"})
    for rota in ("/loja/", "/loja/caneca-azul"):
        html = client_cliente.get(rota).get_data(as_text=True)
        assert 'aria-pressed="true"' in html and "Remover dos favoritos" in html


def test_coracao_pra_visitante_leva_ao_login(client, catalogo):
    html = client.get("/loja/").get_data(as_text=True)
    assert 'href="/entrar?next=/loja/"' in html and "Favoritar" in html
    assert "/conta/favoritos/" not in html


def test_banco_nao_aceita_favorito_duplicado(app, catalogo, criar_usuario):
    u = criar_usuario(email="dup@exemplo.com")
    db.session.add_all([Favorito(user_id=u.id, produto_id=prod().id), Favorito(user_id=u.id, produto_id=prod().id)])
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_excluir_produto_leva_os_favoritos_junto(client_admin, catalogo):
    u = User.query.filter_by(email="admin@exemplo.com").first()
    db.session.add(Favorito(user_id=u.id, produto_id=prod().id))
    db.session.commit()
    client_admin.post(f"/admin/produtos/{prod().id}/excluir")
    assert prod() is None and Favorito.query.count() == 0


def test_produto_ja_vendido_nao_pode_ser_excluido(client_admin, catalogo):
    # SQLite só confere chave estrangeira com o PRAGMA ligado (o Postgres sempre confere)
    db.session.execute(text("PRAGMA foreign_keys=ON"))
    criar_pedido(User.query.filter_by(email="admin@exemplo.com").first())
    html = client_admin.post(f"/admin/produtos/{prod().id}/excluir", follow_redirects=True).get_data(as_text=True)
    assert prod() is not None and "já tem pedidos" in html
    db.session.execute(text("PRAGMA foreign_keys=OFF"))


# ---------- Pedidos ----------

def test_lista_e_detalhe_do_proprio_pedido(client_cliente, catalogo):
    pedido = criar_pedido(eu())
    lista = client_cliente.get("/conta/pedidos").get_data(as_text=True)
    assert f"/conta/pedidos/{pedido.id}" in lista and "R$ 110,00" in lista
    detalhe = client_cliente.get(f"/conta/pedidos/{pedido.id}").get_data(as_text=True)
    assert "Caneca azul" in detalhe and "Pago" in detalhe and "12246-000" in detalhe


def test_pedido_guarda_o_preco_da_epoca(client_cliente, catalogo):
    pedido = criar_pedido(eu(), preco=5500, quantidade=1)
    prod().preco_centavos = 9900
    prod().nome = "Caneca azul (nova versão)"
    db.session.commit()
    html = client_cliente.get(f"/conta/pedidos/{pedido.id}").get_data(as_text=True)
    assert "R$ 55,00" in html and "R$ 99,00" not in html and "nova versão" not in html


def test_conta_resume_ultimo_pedido_endereco_e_favoritos(client_cliente, catalogo):
    criar_pedido(eu())
    client_cliente.post("/conta/endereco", data=ENDERECO_OK)
    client_cliente.post(f"/conta/favoritos/{prod().id}", data={"acao": "adicionar"})
    html = client_cliente.get("/conta").get_data(as_text=True)
    assert "R$ 110,00" in html and "Rua Espanha" in html and "1 peça favoritada" in html


# ---------- Isolamento: A nunca vê dado de B ----------

def test_pedido_de_outro_cliente_da_404(client_cliente, catalogo):
    _, pedido_do_bruno = outra_pessoa()
    assert client_cliente.get(f"/conta/pedidos/{pedido_do_bruno.id}").status_code == 404
    assert client_cliente.get("/conta/pedidos/99999").status_code == 404


def test_listas_do_cliente_nao_mostram_nada_de_outro(client_cliente, catalogo):
    outra_pessoa()
    for rota in ("/conta", "/conta/pedidos", "/conta/favoritos", "/conta/endereco", "/conta/dados", "/loja/"):
        html = client_cliente.get(rota).get_data(as_text=True)
        assert "Bruno" not in html and "Praça da Sé do Bruno" not in html and "Caneca do Bruno" not in html, rota
    assert 'aria-pressed="true"' not in client_cliente.get("/loja/").get_data(as_text=True)


def test_desfavoritar_nao_mexe_no_favorito_de_outro(client_cliente, catalogo):
    bruno, _ = outra_pessoa()
    client_cliente.post(f"/conta/favoritos/{prod().id}", data={"acao": "remover"})
    assert Favorito.query.filter_by(user_id=bruno.id).count() == 1


# ---------- Regras que surgiram na implementação ----------

def test_tira_dos_favoritos_peca_que_saiu_da_loja(client_cliente, catalogo):
    pid = prod().id
    client_cliente.post(f"/conta/favoritos/{pid}", data={"acao": "adicionar"})
    prod().ativo = False
    db.session.commit()
    html = client_cliente.get("/conta/favoritos").get_data(as_text=True)
    assert "Não estão mais à venda" in html and "Caneca azul" in html
    client_cliente.post(f"/conta/favoritos/{pid}", data={"acao": "remover"})
    assert Favorito.query.count() == 0


def test_data_br_usa_horario_de_brasilia():
    from datetime import datetime, timezone

    from app.utils import data_br

    meia_noite_e_meia_utc = datetime(2026, 11, 15, 0, 30, tzinfo=timezone.utc)
    assert data_br(meia_noite_e_meia_utc) == "14/11/2026"  # ainda é dia 14 em Brasília
    assert data_br(meia_noite_e_meia_utc.replace(tzinfo=None), com_hora=True) == "14/11/2026 às 21:30"
    assert data_br(None) == ""


def test_lista_de_pedidos_tem_link_de_verdade(client_cliente, catalogo):
    pedido = criar_pedido(eu())
    html = client_cliente.get("/conta/pedidos").get_data(as_text=True)
    assert f'<a class="lista-pedidos__link" href="/conta/pedidos/{pedido.id}">' in html
