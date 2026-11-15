"""Painel da Julia: pedidos (lista, filtro, detalhe, status) e números do dia/mês.

Ciclo de vida (o servidor só aceita estas transições):
  aguardando_pagamento -> cancelado            (pago só pelo Mercado Pago, nunca à mão)
  pago -> enviado (entrega) | entregue (retirada) | cancelado (peças voltam ao estoque)
  enviado -> entregue ; entregue e cancelado são finais
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.extensions import db
from app.models import EventoPagamento, HistoricoStatus, ItemPedido, Pedido, Product, User
from app.services import mercadopago
from app.services.painel import numeros

UTC = timezone.utc


def prod(slug="caneca-azul"):
    return Product.query.filter_by(slug=slug).first()


def cliente(email="ana@exemplo.com", nome="Ana Cliente", telefone="12991112222"):
    u = User.query.filter_by(email=email).first()
    if u is None:
        u = User(nome=nome, email=email, telefone=telefone)
        u.set_password("senha-segura-123")
        db.session.add(u)
        db.session.commit()
    return u


def pedido(status="pago", entrega="entrega", total=5500, pago_em=None, quantidade=1, usuario=None, **extra):
    usuario = usuario or cliente()
    p = Pedido(user_id=usuario.id, status=status, entrega_tipo=entrega, subtotal_centavos=total,
               frete_centavos=0, total_centavos=total, pago_em=pago_em, **extra)
    if entrega == "entrega":
        p.entrega_cep, p.entrega_logradouro, p.entrega_numero = "12246000", "Rua das Flores", "10"
        p.entrega_bairro, p.entrega_cidade, p.entrega_uf = "Centro", "Taubaté", "SP"
    p.itens.append(ItemPedido(produto_id=prod().id, nome_produto="Caneca azul", preco_unitario_centavos=total,
                              preco_original_centavos=None, quantidade=quantidade))
    db.session.add(p)
    db.session.commit()
    return p


def mudar(client, p, status):
    return client.post(f"/admin/pedidos/{p.id}/status", data={"status": status}, follow_redirects=True)


# ---------- Acesso ----------

def test_pedidos_exige_login(client):
    assert client.get("/admin/pedidos").status_code == 302


def test_cliente_nao_ve_pedidos_do_painel(client_cliente, catalogo):
    p = pedido()
    assert client_cliente.get("/admin/pedidos").status_code == 403
    assert client_cliente.get(f"/admin/pedidos/{p.id}").status_code == 403
    assert client_cliente.post(f"/admin/pedidos/{p.id}/status", data={"status": "enviado"}).status_code == 403
    assert db.session.get(Pedido, p.id).status == "pago"


# ---------- Lista ----------

def test_lista_mostra_pedidos_com_cliente_total_e_status(client_admin, catalogo):
    pedido(status="pago", total=5500)
    pedido(status="aguardando_pagamento", total=7200)
    html = client_admin.get("/admin/pedidos").get_data(as_text=True)
    assert "Ana Cliente" in html and "R$ 55,00" in html and "R$ 72,00" in html
    assert "Pago" in html and "Aguardando pagamento" in html


def test_filtro_por_status_com_contadores(client_admin, catalogo):
    pedido(status="pago", total=1111)
    pedido(status="pago", total=2222)
    pedido(status="enviado", total=3333)
    html = client_admin.get("/admin/pedidos?status=pago").get_data(as_text=True)
    assert "R$ 11,11" in html and "R$ 22,22" in html and "R$ 33,33" not in html
    assert "Pago (2)" in html and "Enviado (1)" in html


def test_busca_por_numero_nome_ou_email(client_admin, catalogo):
    p = pedido(total=1111)
    pedido(total=2222, usuario=cliente("bruno@exemplo.com", "Bruno Silva"))
    assert "R$ 22,22" not in client_admin.get(f"/admin/pedidos?q={p.id}").get_data(as_text=True)
    html = client_admin.get("/admin/pedidos?q=bruno").get_data(as_text=True)
    assert "R$ 22,22" in html and "R$ 11,11" not in html
    assert "R$ 11,11" not in client_admin.get("/admin/pedidos?q=%25").get_data(as_text=True)  # % é texto


def test_paginacao(client_admin, catalogo):
    for i in range(35):
        pedido(total=1000 + i)
    assert client_admin.get("/admin/pedidos").get_data(as_text=True).count('class="linha-pedido"') == 30
    assert client_admin.get("/admin/pedidos?pagina=2").get_data(as_text=True).count('class="linha-pedido"') == 5


def test_lista_avisa_estoque_insuficiente(client_admin, catalogo):
    pedido(estoque_insuficiente=True)
    assert "Estoque insuficiente" in client_admin.get("/admin/pedidos").get_data(as_text=True)


# ---------- Detalhe ----------

def test_detalhe_tem_cliente_itens_entrega_e_pagamento(client_admin, catalogo):
    p = pedido(mp_payment_id="555")
    db.session.add(EventoPagamento(pedido_id=p.id, mp_payment_id="555", status="approved", valor_centavos=5500))
    db.session.commit()
    html = client_admin.get(f"/admin/pedidos/{p.id}").get_data(as_text=True)
    for texto in ("Ana Cliente", "ana@exemplo.com", "(12) 99111-2222", "Caneca azul", "Rua das Flores",
                  "12246-000", "555", "approved"):
        assert texto in html, texto
    assert "https://wa.me/5512991112222?text=" in html


def test_detalhe_sem_telefone_nao_tem_botao_de_whatsapp(client_admin, catalogo):
    p = pedido(usuario=cliente("sem@exemplo.com", "Sem Fone", telefone=None))
    html = client_admin.get(f"/admin/pedidos/{p.id}").get_data(as_text=True)
    assert "Avisar no WhatsApp" not in html and "sem telefone" in html


def test_detalhe_avisa_estorno(client_admin, catalogo):
    p = pedido(mp_payment_id="9")
    db.session.add(EventoPagamento(pedido_id=p.id, mp_payment_id="9", status="refunded", valor_centavos=5500))
    db.session.commit()
    assert "estorno" in client_admin.get(f"/admin/pedidos/{p.id}").get_data(as_text=True).lower()


def test_detalhe_so_mostra_botoes_permitidos(client_admin, catalogo):
    html = client_admin.get(f"/admin/pedidos/{pedido(status='pago', entrega='entrega').id}").get_data(as_text=True)
    assert 'value="enviado"' in html and 'value="cancelado"' in html and 'value="entregue"' not in html
    html = client_admin.get(f"/admin/pedidos/{pedido(status='pago', entrega='retirada').id}").get_data(as_text=True)
    assert 'value="entregue"' in html and 'value="enviado"' not in html
    html = client_admin.get(f"/admin/pedidos/{pedido(status='entregue').id}").get_data(as_text=True)
    assert 'name="status"' not in html


def test_pedido_inexistente_da_404(client_admin):
    assert client_admin.get("/admin/pedidos/99999").status_code == 404


# ---------- Mudança de status ----------

@pytest.mark.parametrize("de, entrega, para", [
    ("pago", "entrega", "enviado"), ("enviado", "entrega", "entregue"),
    ("pago", "retirada", "entregue"), ("aguardando_pagamento", "entrega", "cancelado"),
])
def test_transicoes_permitidas(client_admin, catalogo, de, entrega, para):
    p = pedido(status=de, entrega=entrega)
    mudar(client_admin, p, para)
    assert db.session.get(Pedido, p.id).status == para


@pytest.mark.parametrize("de, entrega, para", [
    ("aguardando_pagamento", "entrega", "pago"),       # pago só pelo Mercado Pago
    ("aguardando_pagamento", "entrega", "enviado"),
    ("pago", "entrega", "entregue"),                    # entrega passa por "enviado"
    ("pago", "retirada", "enviado"),                    # retirada não é enviada
    ("entregue", "entrega", "cancelado"), ("cancelado", "entrega", "pago"),
    ("pago", "entrega", "qualquer-coisa"),
])
def test_transicoes_proibidas(client_admin, catalogo, de, entrega, para):
    p = pedido(status=de, entrega=entrega)
    html = mudar(client_admin, p, para).get_data(as_text=True)
    assert db.session.get(Pedido, p.id).status == de and "aviso--erro" in html


def test_cancelar_pedido_pago_devolve_estoque(client_admin, catalogo):
    p = pedido(status="pago", quantidade=2)  # estoque da caneca: 3
    mudar(client_admin, p, "cancelado")
    assert prod().estoque == 5


def test_cancelar_aguardando_nao_mexe_no_estoque(client_admin, catalogo):
    p = pedido(status="aguardando_pagamento", quantidade=2)
    mudar(client_admin, p, "cancelado")
    assert prod().estoque == 3


def test_cancelar_pedido_com_estoque_insuficiente_pede_conferencia(client_admin, catalogo):
    p = pedido(status="pago", quantidade=2, estoque_insuficiente=True)
    html = mudar(client_admin, p, "cancelado").get_data(as_text=True)
    assert prod().estoque == 3 and "confira o estoque" in html.lower()


def test_historico_registra_quem_mudou(client_admin, catalogo):
    p = pedido(status="pago")
    mudar(client_admin, p, "enviado")
    h = HistoricoStatus.query.filter_by(pedido_id=p.id).one()
    assert (h.de, h.para, h.origem) == ("pago", "enviado", "painel")
    assert h.por.email == "admin@exemplo.com"
    assert "Pessoa Teste" in client_admin.get(f"/admin/pedidos/{p.id}").get_data(as_text=True)  # nome do admin


def test_aprovacao_do_mercado_pago_entra_no_historico(app, catalogo, monkeypatch):
    p = pedido(status="aguardando_pagamento")
    monkeypatch.setattr(mercadopago, "_requisicao", lambda *a, **k: {
        "id": 1, "status": "approved", "external_reference": str(p.id), "transaction_amount": 55.0, "currency_id": "BRL"})
    mercadopago.processar_pagamento("1")
    h = HistoricoStatus.query.filter_by(pedido_id=p.id).one()
    assert (h.de, h.para, h.origem, h.por_user_id) == ("aguardando_pagamento", "pago", "mercado_pago", None)


def test_cliente_ve_o_status_novo(client_admin, catalogo):
    p = pedido(status="pago")
    mudar(client_admin, p, "enviado")
    assert db.session.get(Pedido, p.id).status_texto == "Enviado"


# ---------- Números do painel ----------

# "Agora" fixo: 15/11/2026 às 12:00 em Brasília (15:00 UTC)
AGORA = datetime(2026, 11, 15, 15, 0, tzinfo=UTC)


def test_numeros_do_dia_e_do_mes_no_horario_de_brasilia(app, catalogo):
    pedido(total=1000, pago_em=datetime(2026, 11, 15, 3, 30, tzinfo=UTC))   # 15/11 00:30 BRT -> hoje
    pedido(total=2000, pago_em=datetime(2026, 11, 15, 2, 30, tzinfo=UTC))   # 14/11 23:30 BRT -> ontem
    pedido(total=4000, pago_em=datetime(2026, 11, 2, 12, 0, tzinfo=UTC), status="entregue")  # novembro
    pedido(total=8000, pago_em=datetime(2026, 11, 1, 2, 0, tzinfo=UTC))    # 31/10 23:00 BRT -> outubro
    pedido(total=9999, status="aguardando_pagamento")
    pedido(total=7777, pago_em=datetime(2026, 11, 10, 12, 0, tzinfo=UTC), status="cancelado")
    n = numeros(agora=AGORA)
    assert (n["hoje_qtd"], n["hoje_total"]) == (1, 1000)
    assert (n["mes_qtd"], n["mes_total"], n["ticket_medio"]) == (3, 7000, 2333)
    assert n["aguardando"] == 1


def test_numeros_de_pendencias(app, catalogo):
    pedido(status="pago", entrega="entrega")
    pedido(status="pago", entrega="retirada")
    pedido(status="enviado")
    pedido(status="pago", estoque_insuficiente=True)
    n = numeros(agora=AGORA)
    assert n["a_preparar"] == 3 and n["a_enviar"] == 2 and n["estoque_insuficiente"] == 1


def test_numeros_sem_pedidos(app):
    n = numeros(agora=AGORA)
    assert n["mes_qtd"] == 0 and n["ticket_medio"] == 0 and n["ultimos"] == []


def test_painel_inicial_mostra_numeros_e_mantem_atalhos(client_admin, catalogo):
    pedido(total=5500, pago_em=datetime.now(UTC) - timedelta(minutes=5))
    html = client_admin.get("/admin/").get_data(as_text=True)
    assert "Hoje" in html and "Este mês" in html and "R$ 55,00" in html
    assert "/admin/pedidos?status=pago" in html  # atalho "a preparar"
    for destino in ("/admin/produtos", "/admin/categorias", "/admin/cursos", "/admin/servicos"):
        assert destino in html
