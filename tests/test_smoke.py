import pytest


@pytest.mark.parametrize(
    "rota",
    ["/", "/loja/", "/cursos", "/servicos", "/pecas-personalizadas", "/sobre",
     "/contato", "/entrar", "/cadastro"],
)
def test_paginas_publicas_abrem(client, catalogo, rota):
    assert client.get(rota).status_code == 200


def test_loja_mostra_so_produtos_ativos(client, catalogo):
    html = client.get("/loja/").get_data(as_text=True)
    assert "Caneca azul" in html
    assert "Caneca oculta" not in html


def test_loja_filtra_por_categoria(client, catalogo):
    assert client.get("/loja/?categoria=canecas").status_code == 200
    assert client.get("/loja/?categoria=nao-existe").status_code == 404


def test_produto_ativo_abre_e_inativo_da_404(client, catalogo):
    assert client.get("/loja/caneca-azul").status_code == 200
    assert client.get("/loja/caneca-oculta").status_code == 404
    assert client.get("/loja/nao-existe").status_code == 404


def test_preco_aparece_formatado(client, catalogo):
    assert "R$ 55,00" in client.get("/loja/caneca-azul").get_data(as_text=True)


def test_cadastro_login_e_logout(client):
    resposta = client.post(
        "/cadastro",
        data={"nome": "Ana", "email": "Ana@Exemplo.com", "senha": "senha-segura-123",
              "confirmacao": "senha-segura-123"},
    )
    assert resposta.status_code == 302  # já entra logada

    assert client.get("/conta").status_code == 200
    assert client.post("/sair").status_code == 302
    assert client.get("/conta").status_code == 302  # voltou a pedir login

    resposta = client.post("/entrar", data={"email": "ana@exemplo.com", "senha": "senha-segura-123"})
    assert resposta.status_code == 302
    assert client.get("/conta").status_code == 200


def test_cadastro_recusa_senha_curta_e_email_repetido(client, criar_usuario):
    criar_usuario(email="ana@exemplo.com")
    curta = client.post("/cadastro", data={"nome": "X", "email": "x@exemplo.com",
                                           "senha": "123", "confirmacao": "123"})
    assert curta.status_code == 200
    repetido = client.post("/cadastro", data={"nome": "Y", "email": "ana@exemplo.com",
                                              "senha": "senha-segura-123",
                                              "confirmacao": "senha-segura-123"})
    assert repetido.status_code == 200


def test_login_com_senha_errada_nao_entra(client, criar_usuario):
    criar_usuario()
    resposta = client.post("/entrar", data={"email": "cliente@exemplo.com", "senha": "errada"})
    assert resposta.status_code == 200
    assert client.get("/conta").status_code == 302


def test_login_nao_redireciona_para_fora_do_site(client, criar_usuario):
    criar_usuario()
    for destino in ["//evil.com", "https://evil.com", "/\\evil.com"]:
        resposta = client.post(
            "/entrar",
            data={"email": "cliente@exemplo.com", "senha": "senha-segura-123", "next": destino},
        )
        assert resposta.status_code == 302
        assert "evil.com" not in resposta.headers["Location"]
        client.post("/sair")


def test_admin_exige_login(client):
    resposta = client.get("/admin/")
    assert resposta.status_code == 302
    assert "/entrar" in resposta.headers["Location"]


def test_admin_nega_cliente_comum(client, criar_usuario):
    criar_usuario()
    client.post("/entrar", data={"email": "cliente@exemplo.com", "senha": "senha-segura-123"})
    assert client.get("/admin/").status_code == 403


def test_admin_abre_para_administrador(client, criar_usuario):
    criar_usuario(email="admin@exemplo.com", admin=True)
    client.post("/entrar", data={"email": "admin@exemplo.com", "senha": "senha-segura-123"})
    assert client.get("/admin/").status_code == 200
