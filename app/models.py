from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db, login_manager
from .lojas import LOJA_PECAS, LOJA_PRODUTOS, LOJAS  # noqa: F401  (usados também por quem importa models)


def agora():
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    criado_em = db.Column(db.DateTime(timezone=True), nullable=False, default=agora)
    # Só dígitos (DDD + número). Opcional.
    telefone = db.Column(db.String(20), nullable=True)

    endereco = db.relationship("Endereco", back_populates="usuario", uselist=False,
                               cascade="all, delete-orphan")
    favoritos = db.relationship("Favorito", back_populates="usuario",
                                cascade="all, delete-orphan")
    pedidos = db.relationship("Pedido", back_populates="usuario",
                              order_by="Pedido.criado_em.desc()")

    def set_password(self, senha):
        self.password_hash = generate_password_hash(senha)

    def check_password(self, senha):
        return check_password_hash(self.password_hash, senha)

    @property
    def is_active(self):
        # O Flask-Login recusa o login de quem retornar False aqui
        return self.ativo


class Category(db.Model):
    __tablename__ = "categories"
    # [back/duas-lojas] Só as duas lojas do ateliê (constraint nova)
    __table_args__ = (db.CheckConstraint("loja IN ('pecas', 'produtos')", name="ck_categories_loja"),)

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False, index=True)
    ativa = db.Column(db.Boolean, nullable=False, default=True)
    # [back/duas-lojas] Coluna nova: em qual loja a categoria aparece. Antes a loja era uma só.
    loja = db.Column(db.String(20), nullable=False, default=LOJA_PECAS, server_default=LOJA_PECAS)

    produtos = db.relationship("Product", back_populates="categoria")


class Product(db.Model):
    __tablename__ = "products"
    __table_args__ = (
        db.CheckConstraint("preco_centavos >= 0", name="ck_products_preco_positivo"),
        db.CheckConstraint("estoque >= 0", name="ck_products_estoque_positivo"),
    )

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    slug = db.Column(db.String(180), unique=True, nullable=False, index=True)
    descricao = db.Column(db.Text, nullable=False, default="")
    # Preço em centavos (inteiro) evita erro de arredondamento com decimais
    preco_centavos = db.Column(db.Integer, nullable=False)
    estoque = db.Column(db.Integer, nullable=False, default=0)
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    criado_em = db.Column(db.DateTime(timezone=True), nullable=False, default=agora)
    categoria_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)

    categoria = db.relationship("Category", back_populates="produtos")
    imagens = db.relationship(
        "ProductImage",
        back_populates="produto",
        order_by="ProductImage.ordem",
        cascade="all, delete-orphan",
    )
    # Excluir o produto leva os favoritos junto. Itens de pedido NÃO: produto
    # já vendido não pode ser excluído (o banco recusa; o painel manda desativar).
    favoritos = db.relationship("Favorito", back_populates="produto",
                                cascade="all, delete-orphan")
    promocoes = db.relationship("Promocao", secondary="promocao_produtos", back_populates="produtos")

    @property
    def disponivel(self):
        return self.ativo and self.estoque > 0

    @property
    def imagem_principal(self):
        return self.imagens[0] if self.imagens else None


class ProductImage(db.Model):
    __tablename__ = "product_images"

    id = db.Column(db.Integer, primary_key=True)
    produto_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    # Caminho dentro de static/ (ex.: 'uploads/caneca.jpg') ou URL completa
    caminho = db.Column(db.String(500), nullable=False)
    alt = db.Column(db.String(200), nullable=False, default="")
    ordem = db.Column(db.Integer, nullable=False, default=0)

    produto = db.relationship("Product", back_populates="imagens")


class Course(db.Model):
    """Curso presencial. A inscrição é feita num formulário externo (Google Forms)."""

    __tablename__ = "courses"

    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(150), nullable=False)
    slug = db.Column(db.String(180), unique=True, nullable=False, index=True)
    descricao = db.Column(db.Text, nullable=False, default="")
    # Opcional: curso pode estar "sob consulta"
    valor_centavos = db.Column(db.Integer, nullable=True)
    duracao = db.Column(db.String(80), nullable=False, default="")
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    promocoes = db.relationship("Promocao", secondary="promocao_cursos", back_populates="cursos")


class Service(db.Model):
    __tablename__ = "services"

    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(150), nullable=False)
    descricao = db.Column(db.Text, nullable=False, default="")
    ativo = db.Column(db.Boolean, nullable=False, default=True)


class Endereco(db.Model):
    """Endereço de entrega. Um por cliente (user_id único): não há ID na URL."""

    __tablename__ = "enderecos"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    cep = db.Column(db.String(8), nullable=False)  # só dígitos
    logradouro = db.Column(db.String(150), nullable=False)
    numero = db.Column(db.String(20), nullable=False)
    complemento = db.Column(db.String(80), nullable=False, default="")
    bairro = db.Column(db.String(80), nullable=False)
    cidade = db.Column(db.String(80), nullable=False)
    uf = db.Column(db.String(2), nullable=False)
    atualizado_em = db.Column(db.DateTime(timezone=True), nullable=False, default=agora, onupdate=agora)

    usuario = db.relationship("User", back_populates="endereco")

    @property
    def cep_formatado(self):
        return f"{self.cep[:5]}-{self.cep[5:]}"


class Favorito(db.Model):
    __tablename__ = "favoritos"
    __table_args__ = (
        db.UniqueConstraint("user_id", "produto_id", name="uq_favoritos_user_produto"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    produto_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    criado_em = db.Column(db.DateTime(timezone=True), nullable=False, default=agora)

    usuario = db.relationship("User", back_populates="favoritos")
    produto = db.relationship("Product", back_populates="favoritos")


class Pedido(db.Model):
    """Pedido é documento: guarda CÓPIA do endereço e dos preços do momento da compra."""

    __tablename__ = "pedidos"

    STATUS = {
        "aguardando_pagamento": "Aguardando pagamento",
        "pago": "Pago",
        "enviado": "Enviado",
        "entregue": "Entregue",
        "cancelado": "Cancelado",
    }

    __table_args__ = (
        db.CheckConstraint(
            "status IN ('aguardando_pagamento', 'pago', 'enviado', 'entregue', 'cancelado')",
            name="ck_pedidos_status",
        ),
        db.CheckConstraint("subtotal_centavos >= 0 AND frete_centavos >= 0 AND total_centavos >= 0",
                           name="ck_pedidos_valores_positivos"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    status = db.Column(db.String(30), nullable=False, default="aguardando_pagamento", index=True)
    subtotal_centavos = db.Column(db.Integer, nullable=False)
    frete_centavos = db.Column(db.Integer, nullable=False, default=0)
    total_centavos = db.Column(db.Integer, nullable=False)

    # Cópia do endereço no momento do pedido (vazio se for retirada no ateliê)
    entrega_cep = db.Column(db.String(8), nullable=True)
    entrega_logradouro = db.Column(db.String(150), nullable=True)
    entrega_numero = db.Column(db.String(20), nullable=True)
    entrega_complemento = db.Column(db.String(80), nullable=True)
    entrega_bairro = db.Column(db.String(80), nullable=True)
    entrega_cidade = db.Column(db.String(80), nullable=True)
    entrega_uf = db.Column(db.String(2), nullable=True)

    # 'retirada' (grátis, no ateliê) ou 'entrega' (frete fixo)
    entrega_tipo = db.Column(db.String(20), nullable=False, default="retirada", server_default="retirada")

    # Mercado Pago. Nada de dado de cartão: só os identificadores da preferência e do pagamento.
    mp_preference_id = db.Column(db.String(80), nullable=True)
    mp_init_point = db.Column(db.String(500), nullable=True)
    mp_payment_id = db.Column(db.String(40), nullable=True, index=True)
    pago_em = db.Column(db.DateTime(timezone=True), nullable=True)
    # Pago, mas a peça acabou antes da aprovação (corrida pela última unidade).
    # A Julia decide no painel: fazer outra peça ou devolver o dinheiro.
    estoque_insuficiente = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())

    criado_em = db.Column(db.DateTime(timezone=True), nullable=False, default=agora, index=True)
    atualizado_em = db.Column(db.DateTime(timezone=True), nullable=False, default=agora, onupdate=agora)

    usuario = db.relationship("User", back_populates="pedidos")
    itens = db.relationship("ItemPedido", back_populates="pedido", order_by="ItemPedido.id",
                            cascade="all, delete-orphan")
    historico = db.relationship("HistoricoStatus", back_populates="pedido",
                                order_by="HistoricoStatus.id", cascade="all, delete-orphan")

    @property
    def status_texto(self):
        return self.STATUS.get(self.status, self.status)

    @property
    def entrega_cep_formatado(self):
        return f"{self.entrega_cep[:5]}-{self.entrega_cep[5:]}" if self.entrega_cep else ""

    @property
    def quantidade_itens(self):
        return sum(item.quantidade for item in self.itens)


class ItemPedido(db.Model):
    __tablename__ = "itens_pedido"
    __table_args__ = (
        db.CheckConstraint("quantidade > 0", name="ck_itens_pedido_quantidade"),
        db.CheckConstraint("preco_unitario_centavos >= 0", name="ck_itens_pedido_preco"),
    )

    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey("pedidos.id"), nullable=False, index=True)
    # Sem ondelete: o banco recusa excluir produto que já foi vendido
    produto_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False, index=True)
    nome_produto = db.Column(db.String(150), nullable=False)
    preco_unitario_centavos = db.Column(db.Integer, nullable=False)
    # Preço sem desconto, só quando a compra foi em promoção ("de R$ 55 por R$ 44")
    preco_original_centavos = db.Column(db.Integer, nullable=True)
    quantidade = db.Column(db.Integer, nullable=False)

    pedido = db.relationship("Pedido", back_populates="itens")
    produto = db.relationship("Product")

    @property
    def subtotal_centavos(self):
        return self.preco_unitario_centavos * self.quantidade


class HistoricoStatus(db.Model):
    """Trilha de auditoria: cada mudança de status do pedido, com origem e (se humano) quem fez."""

    __tablename__ = "historico_status"

    ORIGENS = {"cliente": "Cliente", "mercado_pago": "Mercado Pago", "painel": "Painel"}

    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey("pedidos.id"), nullable=False, index=True)
    de = db.Column(db.String(30), nullable=True)  # None = pedido criado
    para = db.Column(db.String(30), nullable=False)
    origem = db.Column(db.String(20), nullable=False)  # 'cliente', 'mercado_pago' ou 'painel'
    por_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    criado_em = db.Column(db.DateTime(timezone=True), nullable=False, default=agora)

    pedido = db.relationship("Pedido", back_populates="historico")
    por = db.relationship("User")


promocao_produtos = db.Table(
    "promocao_produtos",
    db.Column("promocao_id", db.Integer, db.ForeignKey("promocoes.id", ondelete="CASCADE"), primary_key=True),
    db.Column("produto_id", db.Integer, db.ForeignKey("products.id", ondelete="CASCADE"), primary_key=True),
)

promocao_cursos = db.Table(
    "promocao_cursos",
    db.Column("promocao_id", db.Integer, db.ForeignKey("promocoes.id", ondelete="CASCADE"), primary_key=True),
    db.Column("curso_id", db.Integer, db.ForeignKey("courses.id", ondelete="CASCADE"), primary_key=True),
)


class Promocao(db.Model):
    """Desconto percentual ou em valor fixo, com período, para peças e/ou cursos.

    Quem calcula o preço final é app/services/precos.py (único lugar).
    """

    __tablename__ = "promocoes"
    __table_args__ = (
        db.CheckConstraint(
            "(tipo = 'percentual' AND percentual BETWEEN 1 AND 90 AND valor_centavos IS NULL)"
            " OR (tipo = 'valor' AND valor_centavos > 0 AND percentual IS NULL)",
            name="ck_promocoes_tipo_valor",
        ),
        db.CheckConstraint("fim > inicio", name="ck_promocoes_periodo"),
    )

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), nullable=False)
    tipo = db.Column(db.String(12), nullable=False)  # 'percentual' ou 'valor'
    percentual = db.Column(db.Integer, nullable=True)
    valor_centavos = db.Column(db.Integer, nullable=True)
    # Gravados em UTC; o painel mostra e recebe no horário de Brasília
    inicio = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    fim = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    ativa = db.Column(db.Boolean, nullable=False, default=True)
    criado_em = db.Column(db.DateTime(timezone=True), nullable=False, default=agora)

    produtos = db.relationship("Product", secondary=promocao_produtos, back_populates="promocoes",
                               order_by="Product.nome")
    cursos = db.relationship("Course", secondary=promocao_cursos, back_populates="promocoes",
                             order_by="Course.titulo")

    def aplicar(self, centavos):
        """Preço com o desconto. Percentual arredonda o DESCONTO pra baixo."""
        if self.tipo == "percentual":
            return centavos - (centavos * self.percentual) // 100
        return centavos - self.valor_centavos

    @property
    def selo(self):
        from .utils import brl

        return f"−{self.percentual}%" if self.tipo == "percentual" else f"−{brl(self.valor_centavos)}"

    def situacao(self, momento=None):
        """'desativada', 'agendada', 'valendo' ou 'encerrada' (para o painel)."""
        momento = momento or agora()
        inicio, fim = _utc(self.inicio), _utc(self.fim)
        if not self.ativa:
            return "desativada"
        if momento < inicio:
            return "agendada"
        if momento >= fim:
            return "encerrada"
        return "valendo"


def _utc(momento):
    """SQLite devolve data sem fuso; o que gravamos é sempre UTC."""
    return momento.replace(tzinfo=timezone.utc) if momento.tzinfo is None else momento


class EventoPagamento(db.Model):
    """Cada (pagamento, status) que o Mercado Pago confirmou, uma vez só.

    O UNIQUE é o que torna o webhook idempotente: o mesmo aviso chegando 2x
    (ou webhook + volta do cliente ao mesmo tempo) não processa 2x.
    """

    __tablename__ = "eventos_pagamento"
    __table_args__ = (
        db.UniqueConstraint("mp_payment_id", "status", name="uq_eventos_pagamento_payment_status"),
    )

    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey("pedidos.id"), nullable=False, index=True)
    mp_payment_id = db.Column(db.String(40), nullable=False)
    status = db.Column(db.String(30), nullable=False)
    valor_centavos = db.Column(db.Integer, nullable=False)
    recebido_em = db.Column(db.DateTime(timezone=True), nullable=False, default=agora)

    pedido = db.relationship("Pedido")


@login_manager.user_loader
def carregar_usuario(user_id):
    return db.session.get(User, int(user_id))
