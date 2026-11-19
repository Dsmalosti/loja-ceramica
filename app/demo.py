"""Dados de DEMONSTRAÇÃO (fictícios) para a Julia aprovar o site: `flask seed-demo`.

- Peças com as fotos que já estão em static/img/inicio (WebP leves).
- Cursos, serviços, promoções (uma valendo, uma agendada) e pedidos fictícios em várias
  situações, pra o painel não aparecer vazio.
- Pode rodar de novo: o que já existe (pelo slug/e-mail) não é duplicado.
- Admin de demo só se DEMO_ADMIN_EMAIL e DEMO_ADMIN_SENHA estiverem no ambiente; a senha
  nunca é impressa nem gravada em texto (só o hash).
- Em produção só roda com PERMITIR_SEED_DEMO=1 (ninguém enche a loja real de dados fictícios).

No lançamento de verdade este arquivo pode ser apagado.
"""
import os
import secrets
from datetime import datetime, timedelta, timezone

from .extensions import db
from .lojas import LOJA_PECAS, LOJA_PRODUTOS
from .models import (Category, Course, CourseImage, Endereco, HistoricoStatus, ItemPedido, Pedido, Product,
                     ProductImage, Promocao, Service, User)
from .utils import slugify

FOTO = "img/inicio/"
SENHA_MINIMA_ADMIN = 12

# Cada peça casa com o que a foto mostra (não há foto de caneca entre as de static/img/inicio).
# [back/duas-lojas] Antes era só a lista de nomes: agora cada categoria diz a sua loja.
CATEGORIAS = {
    "Pratos": LOJA_PECAS, "Tigelas": LOJA_PECAS, "Vasos": LOJA_PECAS, "Moringas": LOJA_PECAS,
    "Tintas corantes": LOJA_PRODUTOS, "Kits para ceramistas": LOJA_PRODUTOS,
}

# (nome, categoria, descrição, preço em centavos, estoque, foto)
PECAS = [
    ("Prato raso Eucalipto", "Pratos", "Prato raso de 26 cm, esmalte branco pontilhado e borda irregular.",
     7900, 8, "vertical-pecas-720.webp"),
    ("Prato raso Champanhe", "Pratos", "Prato raso de 26 cm em esmalte champanhe acetinado.",
     7400, 6, "carrossel-pratos-800.webp"),
    ("Prato fundo Areia", "Pratos", "Prato fundo de 21 cm, bom pra sopas e massas. Esmalte areia.",
     8400, 5, "carrossel-pratos-retrato.webp"),
    ("Jogo de 4 pratos de sobremesa", "Pratos", "Quatro pratos de 18 cm, cada um com um tom de esmalte.",
     19900, 2, "carrossel-pratos-1600.webp"),
    ("Trio de tigelinhas Névoa", "Tigelas", "Três tigelinhas de 9 cm em esmalte azul-névoa, pra molhos e petiscos.",
     6900, 0, "vertical-pecas-480.webp"),
    ("Tigela de servir Lótus", "Tigelas", "Tigela de 24 cm pra levar à mesa, com o mesmo esmalte do pote Lótus.",
     14500, 3, "carrossel-vasos-perto-1600.webp"),
    ("Vaso Lótus", "Vasos", "Vaso de 30 cm com flores de lótus em relevo e pintura à mão. Peça única.",
     32000, 1, "carrossel-vasos-perto-800.webp"),
    ("Pote Lótus com tampa", "Vasos", "Pote com tampa e flores de lótus pintadas à mão, pra mantimentos ou decoração.",
     26000, 2, "carrossel-vasos-perto-retrato.webp"),
    ("Moringa Terracota", "Moringas", "Moringa de barro que mantém a água fresquinha. 1,5 litro.",
     15800, 4, "carrossel-vasos-estante-800.webp"),
    ("Jarra rústica", "Moringas", "Jarra de alça em barro aparente, pra água, suco ou flores.",
     12900, 5, "carrossel-vasos-estante-retrato.webp"),
    ("Moringa pintada", "Moringas", "Moringa com faixas pintadas à mão em tons de terra e verde.",
     18500, 3, "carrossel-vasos-estante-1600.webp"),
    # [back/duas-lojas] Itens fictícios da loja de produtos para cerâmica
    ("Tinta corante Azul Cobalto", "Tintas corantes", "Frasco de 100 ml para colorir engobes e esmaltes.",
     3200, 12, "carrossel-tintas-800.webp"),
    ("Tinta corante Verde Musgo", "Tintas corantes", "Frasco de 100 ml, cor intensa depois da queima.",
     3200, 9, "carrossel-tintas-retrato.webp"),
    ("Tinta corante Terracota", "Tintas corantes", "Frasco de 100 ml em tom de barro queimado.",
     2900, 15, "carrossel-tintas-1600.webp"),
    ("Kit círculo de cores", "Kits para ceramistas", "Seis cores básicas para misturar e testar no ateliê.",
     16900, 4, "carrossel-tintas-800.webp"),
    ("Kit primeira pintura", "Kits para ceramistas", "Três cores e orientações para começar a pintar peças.",
     9800, 6, "carrossel-tintas-retrato.webp"),
]

CURSOS = [
    ("Introdução ao torno", "Primeiros passos no torno: centralizar o barro, abrir e levantar a primeira peça.",
     32000, "4 encontros de 3 horas"),
    ("Modelagem manual", "Peças feitas à mão, sem torno: placas, rolinhos e beliscão.", None, "2 encontros"),
    ("Esmaltação e queima", "Como escolher, preparar e aplicar esmaltes, e o que acontece no forno.",
     28000, "3 encontros"),
]

# [back/compra-por-loja] Embalagem fictícia: (peso em g, altura, largura, comprimento em cm)
ENVIO_DEMO = {"Tintas corantes": (150, 12, 5, 5), "Kits para ceramistas": (700, 8, 20, 15)}

# [back/cursos-completos] Turma (aberta?) e fotos de cada curso da demo; quem ensina é um nome genérico
DETALHES_CURSOS = {
    "Introdução ao torno": (True, ["carrossel-aula-800.webp", "vertical-cursos-720.webp"]),
    "Modelagem manual": (True, ["vertical-mesa-720.webp"]),
    "Esmaltação e queima": (False, ["vertical-cursos-480.webp", "carrossel-tintas-800.webp"]),
}
PROFESSOR_DEMO = ("Equipe Malosti", "malosti.loja")

SERVICOS = [
    ("Peças sob encomenda", "Jogos de jantar, canecas personalizadas e presentes, combinados pelo WhatsApp."),
    ("Queima de peças", "Queima de biscoito e de esmalte para quem tem ateliê em casa."),
]


def _agora():
    return datetime.now(timezone.utc)


def _categorias():
    mapa = {}
    for nome, loja in CATEGORIAS.items():
        slug = slugify(nome)
        mapa[nome] = Category.query.filter_by(slug=slug).first() or Category(nome=nome, slug=slug, loja=loja)
        db.session.add(mapa[nome])
    return mapa


def _pecas(categorias):
    for nome, categoria, descricao, preco, estoque, foto in PECAS:
        slug = slugify(nome)
        produto = Product.query.filter_by(slug=slug).first()
        if produto is None:
            produto = Product(nome=nome, slug=slug, descricao=descricao, preco_centavos=preco, estoque=estoque,
                              categoria=categorias[categoria])
            produto.imagens.append(ProductImage(caminho=FOTO + foto, alt="", ordem=0))
            db.session.add(produto)
        if categoria in ENVIO_DEMO and produto.peso_gramas is None:
            produto.peso_gramas, produto.altura_cm, produto.largura_cm, produto.comprimento_cm = ENVIO_DEMO[categoria]


def _cursos_e_servicos():
    for titulo, descricao, valor, duracao in CURSOS:
        curso = Course.query.filter_by(slug=slugify(titulo)).first()
        if curso is None:
            curso = Course(titulo=titulo, slug=slugify(titulo), descricao=descricao,
                           valor_centavos=valor, duracao=duracao)
            db.session.add(curso)
        if not curso.imagens:  # completa também cursos de uma demo antiga
            aberta, fotos = DETALHES_CURSOS[titulo]
            curso.turma_aberta = aberta
            curso.professor_nome, curso.professor_instagram = PROFESSOR_DEMO
            for ordem, foto in enumerate(fotos):
                curso.imagens.append(CourseImage(caminho=FOTO + foto, alt="", ordem=ordem))
    for titulo, descricao in SERVICOS:
        if not Service.query.filter_by(titulo=titulo).first():
            db.session.add(Service(titulo=titulo, descricao=descricao))


def _promocoes(agora):
    if Promocao.query.filter(Promocao.nome.like("%(demo)")).first():
        return
    moringas = Product.query.join(Category).filter(Category.slug == "moringas").all()
    pratos = Product.query.join(Category).filter(Category.slug == "pratos").all()
    torno = Course.query.filter_by(slug=slugify("Introdução ao torno")).all()

    valendo = Promocao(nome="Semana das moringas (demo)", tipo="percentual", percentual=15, ativa=True,
                       inicio=agora - timedelta(days=1), fim=agora + timedelta(days=10))
    valendo.produtos, valendo.cursos = moringas, torno
    agendada = Promocao(nome="Natal no ateliê (demo)", tipo="valor", valor_centavos=2000, ativa=True,
                        inicio=agora + timedelta(days=20), fim=agora + timedelta(days=40))
    agendada.produtos = pratos
    db.session.add_all([valendo, agendada])


def _cliente_e_pedidos(agora):
    email = "cliente.demo@exemplo.com"
    cliente = User.query.filter_by(email=email).first()
    if cliente is None:
        cliente = User(nome="Cliente Demonstração", email=email, telefone="12900000000")
        # Senha aleatória e descartada: ninguém entra nesta conta (a Julia testa criando a dela)
        cliente.set_password(secrets.token_urlsafe(24))
        db.session.add(cliente)
        db.session.flush()
        db.session.add(Endereco(user_id=cliente.id, cep="12246000", logradouro="Rua das Flores (fictícia)",
                                numero="100", bairro="Centro", cidade="São José dos Campos", uf="SP"))
    if Pedido.query.filter_by(user_id=cliente.id).first():
        return

    pecas = {p.slug: p for p in Product.query.all()}
    # [back/compra-por-loja] Pedidos só de produtos e com retirada, como a loja vende agora.
    # (status final, itens [(slug, qtd)], criado há quantos dias)
    roteiro = [
        ("entregue", [("tinta-corante-terracota", 2)], 12),
        ("pago", [("kit-circulo-de-cores", 1), ("tinta-corante-azul-cobalto", 1)], 1),
        ("pago", [("kit-primeira-pintura", 1)], 0),
        ("aguardando_pagamento", [("tinta-corante-verde-musgo", 1)], 0),
        ("cancelado", [("tinta-corante-azul-cobalto", 1)], 6),
    ]
    caminho = {"entregue": ["pago", "entregue"], "pago": ["pago"], "aguardando_pagamento": [], "cancelado": ["cancelado"]}
    for status, itens, dias in roteiro:
        criado = agora - timedelta(days=dias, hours=2)
        pedido = Pedido(user_id=cliente.id, status=status, entrega_tipo="retirada", criado_em=criado,
                        subtotal_centavos=0, frete_centavos=0, total_centavos=0)
        for slug, qtd in itens:
            p = pecas[slug]
            pedido.itens.append(ItemPedido(produto_id=p.id, nome_produto=p.nome,
                                           preco_unitario_centavos=p.preco_centavos, quantidade=qtd))
        pedido.subtotal_centavos = sum(i.subtotal_centavos for i in pedido.itens)
        pedido.total_centavos = pedido.subtotal_centavos
        pedido.historico.append(HistoricoStatus(de=None, para="aguardando_pagamento", origem="cliente",
                                                por_user_id=cliente.id, criado_em=criado))
        anterior, momento = "aguardando_pagamento", criado
        for passo in caminho[status]:
            momento += timedelta(hours=1)
            origem = "mercado_pago" if passo == "pago" else "painel"
            pedido.historico.append(HistoricoStatus(de=anterior, para=passo, origem=origem, criado_em=momento))
            if passo == "pago":
                pedido.pago_em, pedido.mp_payment_id = momento, f"demo-{secrets.randbelow(10**9)}"
            anterior = passo
        db.session.add(pedido)


def _admin_de_demo():
    """Devolve uma mensagem pro terminal (sem a senha)."""
    email = (os.environ.get("DEMO_ADMIN_EMAIL") or "").strip().lower()
    senha = os.environ.get("DEMO_ADMIN_SENHA") or ""
    if not email or not senha:
        return "Admin de demo: DEMO_ADMIN_EMAIL/DEMO_ADMIN_SENHA não definidos; nenhum admin criado."
    if len(senha) < SENHA_MINIMA_ADMIN:
        return f"Admin de demo NÃO criado: a senha precisa ter pelo menos {SENHA_MINIMA_ADMIN} caracteres."
    if User.query.filter_by(email=email).first():
        return f"Admin de demo já existe ({email}); senha mantida."
    admin = User(nome="Admin Demonstração", email=email, is_admin=True)
    admin.set_password(senha)
    db.session.add(admin)
    return f"Admin de demo criado: {email} (a senha está só no ambiente)."


def semear(app_env):
    """Roda o seed de demo. Devolve as linhas pra mostrar no terminal."""
    if app_env == "production" and os.environ.get("PERMITIR_SEED_DEMO") != "1":
        return ["Bloqueado em produção: defina PERMITIR_SEED_DEMO=1 só no ambiente da DEMO."]
    agora = _agora()
    categorias = _categorias()
    db.session.flush()
    _pecas(categorias)
    _cursos_e_servicos()
    db.session.flush()
    _promocoes(agora)
    _cliente_e_pedidos(agora)
    mensagem_admin = _admin_de_demo()
    db.session.commit()
    return [
        f"Demo pronta: {Product.query.count()} itens na loja, {Course.query.count()} cursos, "
        f"{Promocao.query.count()} promoções, {Pedido.query.count()} pedidos.",
        mensagem_admin,
    ]
