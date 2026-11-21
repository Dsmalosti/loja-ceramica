from flask import flash, redirect, render_template, request, url_for

from ..extensions import db
from ..models import Service
from ..services.imagens import ErroArmazenamento, ImagemInvalida, gravar_imagem, preparar_imagem, remover_imagem
from ..validators import validar_servico
from .admin import bp

# [back/painel-julia] Serviço ganhou foto e posição na página. Antes era só título e descrição,
# em ordem alfabética, e criar/editar copiavam os campos cada um na sua rota.


def _valores(servico=None):
    if servico is None:
        return {"titulo": "", "descricao": "", "ativo": True, "ordem_texto": ""}
    return {"titulo": servico.titulo, "descricao": servico.descricao, "ativo": servico.ativo,
            "ordem_texto": str(servico.ordem)}


def _salvar(servico):
    """Cria (servico=None) ou edita. Valida a foto ANTES de gravar; apaga a antiga só depois do commit."""
    dados, erros = validar_servico(request.form)
    foto_nova = None
    arquivo = request.files.get("foto")
    if arquivo and arquivo.filename:
        try:
            foto_nova = preparar_imagem(arquivo)
        except ImagemInvalida as erro:
            erros.append(str(erro))
    if erros:
        for erro in erros:
            flash(erro, "erro")
        return None, dados

    if servico is None:
        servico = Service()
        db.session.add(servico)
    servico.titulo = dados["titulo"]
    servico.descricao = dados["descricao"]
    servico.ativo = dados["ativo"]
    servico.ordem = dados["ordem"]

    gravada, apagar = None, None
    try:
        gravada = gravar_imagem(*foto_nova) if foto_nova else None
    except ErroArmazenamento as erro:
        db.session.rollback()
        flash(str(erro), "erro")
        return None, dados
    if gravada or dados["remover_foto"]:
        apagar = servico.foto or None
        servico.foto = gravada or ""
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        if gravada:
            remover_imagem(gravada)
        raise
    if apagar:
        remover_imagem(apagar)
    return servico, dados


@bp.route("/servicos")
def servicos_lista():
    servicos = Service.query.order_by(Service.ordem, Service.titulo).all()
    return render_template("admin/servicos_lista.html", servicos=servicos)


@bp.route("/servicos/novo", methods=["GET", "POST"])
def servico_novo():
    valores = _valores()
    if request.method == "POST":
        salvo, valores = _salvar(None)
        if salvo:
            flash("Serviço criado.", "ok")
            return redirect(url_for("admin.servicos_lista"))
    return render_template("admin/servico_form.html", servico=None, valores=valores)


@bp.route("/servicos/<int:servico_id>/editar", methods=["GET", "POST"])
def servico_editar(servico_id):
    servico = db.get_or_404(Service, servico_id)
    valores = _valores(servico)
    if request.method == "POST":
        salvo, valores = _salvar(servico)
        if salvo:
            flash("Serviço salvo.", "ok")
            return redirect(url_for("admin.servicos_lista"))
    return render_template("admin/servico_form.html", servico=servico, valores=valores)


@bp.route("/servicos/<int:servico_id>/alternar", methods=["POST"])
def servico_alternar(servico_id):
    servico = db.get_or_404(Service, servico_id)
    servico.ativo = not servico.ativo
    db.session.commit()
    flash(f"Serviço “{servico.titulo}” {'ativado' if servico.ativo else 'desativado'}.", "ok")
    return redirect(url_for("admin.servicos_lista"))


@bp.route("/servicos/<int:servico_id>/excluir", methods=["POST"])
def servico_excluir(servico_id):
    servico = db.get_or_404(Service, servico_id)
    titulo, foto = servico.titulo, servico.foto
    db.session.delete(servico)
    db.session.commit()
    if foto:
        remover_imagem(foto)  # [back/painel-julia] a foto vai junto
    flash(f"Serviço “{titulo}” excluído.", "ok")
    return redirect(url_for("admin.servicos_lista"))
