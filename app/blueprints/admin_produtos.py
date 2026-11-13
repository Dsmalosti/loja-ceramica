from flask import abort, flash, redirect, render_template, request, url_for
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import Category, Product, ProductImage
from ..services.catalogo import slug_unico
from ..services.imagens import (
    MAX_IMAGENS_POR_PRODUTO,
    ImagemInvalida,
    gravar_imagem,
    preparar_imagem,
    remover_imagem,
)
from ..validators import escapar_like, formatar_preco_input, validar_produto
from .admin import bp

STATUS_VALIDOS = ("ativos", "inativos", "sem-estoque")


def _categorias():
    return Category.query.order_by(Category.nome).all()


def _valores_padrao():
    return {
        "nome": "",
        "descricao": "",
        "preco_texto": "",
        "estoque_texto": "0",
        "categoria_id": "",
        "ativo": True,
    }


def _valores_do_produto(produto):
    return {
        "nome": produto.nome,
        "descricao": produto.descricao,
        "preco_texto": formatar_preco_input(produto.preco_centavos),
        "estoque_texto": str(produto.estoque),
        "categoria_id": str(produto.categoria_id),
        "ativo": produto.ativo,
    }


def _erros_da_categoria(dados):
    """A categoria escolhida precisa existir (o validador só confere o formato)."""
    categoria_id = dados["categoria_id_int"]
    if categoria_id is not None and db.session.get(Category, categoria_id) is None:
        return ["A categoria escolhida não existe mais. Escolha outra."]
    return []


def _preparar_uploads(ja_existentes=0):
    """Valida todas as fotos do envio antes de gravar qualquer coisa."""
    arquivos = [a for a in request.files.getlist("imagens") if a and a.filename]
    if ja_existentes + len(arquivos) > MAX_IMAGENS_POR_PRODUTO:
        return [], [f"Cada produto aceita até {MAX_IMAGENS_POR_PRODUTO} fotos."]

    prontas, erros = [], []
    for arquivo in arquivos:
        try:
            prontas.append(preparar_imagem(arquivo))
        except ImagemInvalida as erro:
            erros.append(str(erro))
    return prontas, erros


def _anexar_fotos(produto, prontas):
    """Grava as fotos em disco e liga ao produto. Devolve os caminhos gravados."""
    caminhos = []
    ordem = max((imagem.ordem for imagem in produto.imagens), default=-1) + 1
    for conteudo, extensao in prontas:
        caminho = gravar_imagem(conteudo, extensao)
        caminhos.append(caminho)
        # alt vazio: o site usa o nome do produto, que acompanha renomeações
        produto.imagens.append(ProductImage(caminho=caminho, alt="", ordem=ordem))
        ordem += 1
    return caminhos


def _salvar(caminhos_gravados):
    """Commit que não deixa fotos órfãs no disco se o banco recusar."""
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        for caminho in caminhos_gravados:
            remover_imagem(caminho)
        raise


@bp.route("/produtos")
def produtos_lista():
    busca = request.args.get("q", "").strip()
    categoria_id = request.args.get("categoria", type=int)
    status = request.args.get("status", "")

    consulta = Product.query.join(Category)
    if busca:
        consulta = consulta.filter(Product.nome.ilike(f"%{escapar_like(busca)}%", escape="\\"))
    if categoria_id:
        consulta = consulta.filter(Product.categoria_id == categoria_id)
    if status == "ativos":
        consulta = consulta.filter(Product.ativo.is_(True))
    elif status == "inativos":
        consulta = consulta.filter(Product.ativo.is_(False))
    elif status == "sem-estoque":
        consulta = consulta.filter(Product.estoque == 0)

    return render_template(
        "admin/produtos_lista.html",
        produtos=consulta.order_by(Product.nome).all(),
        categorias=_categorias(),
        filtros={"q": busca, "categoria": categoria_id, "status": status if status in STATUS_VALIDOS else ""},
    )


@bp.route("/produtos/novo", methods=["GET", "POST"])
def produto_novo():
    categorias = _categorias()
    valores = _valores_padrao()

    if request.method == "POST":
        dados, erros = validar_produto(request.form)
        valores = dados
        erros += _erros_da_categoria(dados)
        prontas, erros_fotos = _preparar_uploads()
        erros += erros_fotos

        if not erros:
            produto = Product(
                nome=dados["nome"],
                slug=slug_unico(Product, dados["nome"]),
                descricao=dados["descricao"],
                preco_centavos=dados["preco_centavos"],
                estoque=dados["estoque"],
                ativo=dados["ativo"],
                categoria_id=dados["categoria_id_int"],
            )
            db.session.add(produto)
            caminhos = _anexar_fotos(produto, prontas)
            _salvar(caminhos)
            flash("Produto criado. Se quiser, adicione mais fotos abaixo.", "ok")
            return redirect(url_for("admin.produto_editar", produto_id=produto.id))
        for erro in erros:
            flash(erro, "erro")

    return render_template(
        "admin/produto_form.html",
        produto=None,
        valores=valores,
        categorias=categorias,
        max_imagens=MAX_IMAGENS_POR_PRODUTO,
    )


@bp.route("/produtos/<int:produto_id>/editar", methods=["GET", "POST"])
def produto_editar(produto_id):
    produto = db.get_or_404(Product, produto_id)
    categorias = _categorias()
    valores = _valores_do_produto(produto)

    if request.method == "POST":
        dados, erros = validar_produto(request.form)
        valores = dados
        erros += _erros_da_categoria(dados)

        if not erros:
            # O slug não muda ao renomear, para não quebrar links já compartilhados
            produto.nome = dados["nome"]
            produto.descricao = dados["descricao"]
            produto.preco_centavos = dados["preco_centavos"]
            produto.estoque = dados["estoque"]
            produto.ativo = dados["ativo"]
            produto.categoria_id = dados["categoria_id_int"]
            db.session.commit()
            flash("Produto salvo.", "ok")
            return redirect(url_for("admin.produto_editar", produto_id=produto.id))
        for erro in erros:
            flash(erro, "erro")

    return render_template(
        "admin/produto_form.html",
        produto=produto,
        valores=valores,
        categorias=categorias,
        max_imagens=MAX_IMAGENS_POR_PRODUTO,
    )


@bp.route("/produtos/<int:produto_id>/alternar", methods=["POST"])
def produto_alternar(produto_id):
    produto = db.get_or_404(Product, produto_id)
    produto.ativo = not produto.ativo
    db.session.commit()
    if produto.ativo:
        flash(f"“{produto.nome}” voltou para a loja.", "ok")
    else:
        flash(f"“{produto.nome}” foi desativado e não aparece mais na loja.", "ok")
    return redirect(url_for("admin.produtos_lista"))


@bp.route("/produtos/<int:produto_id>/excluir", methods=["POST"])
def produto_excluir(produto_id):
    produto = db.get_or_404(Product, produto_id)
    nome = produto.nome
    caminhos = [imagem.caminho for imagem in produto.imagens]

    try:
        db.session.delete(produto)
        db.session.commit()
    except IntegrityError:
        # Quando existirem pedidos, produto já vendido não pode sumir: só desativar
        db.session.rollback()
        flash(f"“{nome}” não pode ser excluído porque já tem pedidos. Desative-o.", "erro")
        return redirect(url_for("admin.produtos_lista"))

    for caminho in caminhos:
        remover_imagem(caminho)
    flash(f"“{nome}” foi excluído.", "ok")
    return redirect(url_for("admin.produtos_lista"))


# ---------- Fotos do produto ----------

@bp.route("/produtos/<int:produto_id>/imagens", methods=["POST"])
def produto_imagens_adicionar(produto_id):
    produto = db.get_or_404(Product, produto_id)
    prontas, erros = _preparar_uploads(ja_existentes=len(produto.imagens))
    if not erros and not prontas:
        erros.append("Escolha pelo menos uma foto para enviar.")

    if erros:
        for erro in erros:
            flash(erro, "erro")
    else:
        caminhos = _anexar_fotos(produto, prontas)
        _salvar(caminhos)
        flash("Fotos adicionadas.", "ok")
    return redirect(url_for("admin.produto_editar", produto_id=produto.id))


@bp.route("/produtos/<int:produto_id>/imagens/<int:imagem_id>/excluir", methods=["POST"])
def produto_imagem_excluir(produto_id, imagem_id):
    imagem = ProductImage.query.filter_by(id=imagem_id, produto_id=produto_id).first_or_404()
    caminho = imagem.caminho
    db.session.delete(imagem)
    db.session.commit()
    remover_imagem(caminho)
    flash("Foto removida.", "ok")
    return redirect(url_for("admin.produto_editar", produto_id=produto_id))


@bp.route("/produtos/<int:produto_id>/imagens/<int:imagem_id>/principal", methods=["POST"])
def produto_imagem_principal(produto_id, imagem_id):
    produto = db.get_or_404(Product, produto_id)
    alvo = next((i for i in produto.imagens if i.id == imagem_id), None)
    if alvo is None:
        abort(404)

    # A primeira da lista é a foto principal (a que aparece na loja)
    ordenadas = [alvo] + [i for i in produto.imagens if i.id != alvo.id]
    for posicao, imagem in enumerate(ordenadas):
        imagem.ordem = posicao
    db.session.commit()
    flash("Foto principal atualizada.", "ok")
    return redirect(url_for("admin.produto_editar", produto_id=produto_id))
