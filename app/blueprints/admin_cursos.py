from flask import flash, redirect, render_template, request, url_for

from ..extensions import db
from ..models import Course, CourseImage
from ..services.catalogo import slug_unico
from ..services.imagens import ErroArmazenamento, ImagemInvalida, gravar_imagem, preparar_imagem, remover_imagem
from ..validators import formatar_preco_input, validar_curso
from .admin import bp

# [back/cursos-completos] Fotos do curso e de quem ensina. Antes o curso não tinha foto.
MAX_FOTOS_CURSO = 6


def _valores_padrao():
    return {"titulo": "", "descricao": "", "duracao": "", "valor_texto": "", "ativo": True,
            "turma": "aberta", "professor_nome": "", "professor_instagram": ""}


def _valores_do_curso(curso):
    return {
        "titulo": curso.titulo,
        "descricao": curso.descricao,
        "duracao": curso.duracao,
        "valor_texto": formatar_preco_input(curso.valor_centavos),
        "ativo": curso.ativo,
        # [back/cursos-completos] campos novos
        "turma": "aberta" if curso.turma_aberta else "fechada",
        "professor_nome": curso.professor_nome,
        "professor_instagram": curso.professor_instagram,
    }


def _ler_fotos(curso):
    """Valida todas as fotos do envio antes de gravar qualquer coisa.

    Devolve (novas, foto_do_professor, imagens_a_remover, erros).
    """
    erros, novas, professor = [], [], None
    for arquivo in [a for a in request.files.getlist("fotos") if a and a.filename]:
        try:
            novas.append(preparar_imagem(arquivo))
        except ImagemInvalida as erro:
            erros.append(str(erro))
    arquivo = request.files.get("professor_foto")
    if arquivo and arquivo.filename:
        try:
            professor = preparar_imagem(arquivo)
        except ImagemInvalida as erro:
            erros.append(str(erro))

    # Só remove foto DESTE curso: id de outro curso é ignorado
    existentes = {imagem.id: imagem for imagem in curso.imagens} if curso else {}
    remover = [existentes[int(v)] for v in request.form.getlist("remover_fotos") if v.isdigit() and int(v) in existentes]
    if len(existentes) - len(remover) + len(novas) > MAX_FOTOS_CURSO:
        erros.append(f"Cada curso aceita até {MAX_FOTOS_CURSO} fotos.")
    return novas, professor, remover, erros


def _aplicar(curso, dados, novas, professor, remover):
    """Grava os arquivos novos e atualiza o curso. Devolve (gravados, a_apagar_depois_do_commit)."""
    curso.titulo = dados["titulo"]
    curso.descricao = dados["descricao"]
    curso.duracao = dados["duracao"]
    curso.valor_centavos = dados["valor_centavos"]
    curso.ativo = dados["ativo"]
    curso.turma_aberta = dados["turma_aberta"]
    curso.professor_nome = dados["professor_nome"]
    curso.professor_instagram = dados["professor_instagram_perfil"]

    gravados = []
    try:
        foto_professor = gravar_imagem(*professor) if professor else None
        if foto_professor:
            gravados.append(foto_professor)
        fotos = [gravar_imagem(conteudo, extensao) for conteudo, extensao in novas]
    except ErroArmazenamento:
        for caminho in gravados:  # nada de foto órfã se o armazenamento cair no meio
            remover_imagem(caminho)
        raise
    gravados += fotos

    apagar = [imagem.caminho for imagem in remover]
    for imagem in remover:
        curso.imagens.remove(imagem)
    if foto_professor or dados["remover_foto_professor"]:
        if curso.professor_foto:
            apagar.append(curso.professor_foto)
        curso.professor_foto = foto_professor or ""
    ordem = max((imagem.ordem for imagem in curso.imagens), default=-1) + 1
    for posicao, caminho in enumerate(fotos):
        curso.imagens.append(CourseImage(caminho=caminho, alt="", ordem=ordem + posicao))
    return gravados, apagar


def _salvar(curso):
    """Cria (curso=None) ou edita. Devolve (curso salvo ou None, valores para o formulário)."""
    dados, erros = validar_curso(request.form)
    novas, professor, remover, erros_fotos = _ler_fotos(curso)
    erros += erros_fotos
    if erros:
        for erro in erros:
            flash(erro, "erro")
        return None, dados

    if curso is None:
        curso = Course(slug=slug_unico(Course, dados["titulo"]))
        db.session.add(curso)
    try:
        gravados, apagar = _aplicar(curso, dados, novas, professor, remover)
    except ErroArmazenamento as erro:
        db.session.rollback()
        flash(str(erro), "erro")
        return None, dados
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        for caminho in gravados:
            remover_imagem(caminho)
        raise
    for caminho in apagar:
        remover_imagem(caminho)
    return curso, dados


@bp.route("/cursos")
def cursos_lista():
    cursos = Course.query.order_by(Course.titulo).all()
    return render_template("admin/cursos_lista.html", cursos=cursos)


@bp.route("/cursos/novo", methods=["GET", "POST"])
def curso_novo():
    valores = _valores_padrao()
    if request.method == "POST":
        # [back/cursos-completos] Antes criava aqui direto, sem fotos nem professor
        salvo, valores = _salvar(None)
        if salvo:
            flash("Curso criado.", "ok")
            return redirect(url_for("admin.cursos_lista"))
    return render_template("admin/curso_form.html", curso=None, valores=valores, max_fotos=MAX_FOTOS_CURSO)


@bp.route("/cursos/<int:curso_id>/editar", methods=["GET", "POST"])
def curso_editar(curso_id):
    curso = db.get_or_404(Course, curso_id)
    valores = _valores_do_curso(curso)
    if request.method == "POST":
        # [back/cursos-completos] Antes copiava os campos aqui; agora _salvar cuida também das fotos
        salvo, valores = _salvar(curso)
        if salvo:
            flash("Curso salvo.", "ok")
            return redirect(url_for("admin.cursos_lista"))
    return render_template("admin/curso_form.html", curso=curso, valores=valores, max_fotos=MAX_FOTOS_CURSO)


@bp.route("/cursos/<int:curso_id>/alternar", methods=["POST"])
def curso_alternar(curso_id):
    curso = db.get_or_404(Course, curso_id)
    curso.ativo = not curso.ativo
    db.session.commit()
    flash(f"Curso “{curso.titulo}” {'ativado' if curso.ativo else 'desativado'}.", "ok")
    return redirect(url_for("admin.cursos_lista"))


@bp.route("/cursos/<int:curso_id>/excluir", methods=["POST"])
def curso_excluir(curso_id):
    curso = db.get_or_404(Course, curso_id)
    titulo = curso.titulo
    # [back/cursos-completos] Apaga os arquivos depois que o banco confirmar
    caminhos = [imagem.caminho for imagem in curso.imagens] + ([curso.professor_foto] if curso.professor_foto else [])
    db.session.delete(curso)
    db.session.commit()
    for caminho in caminhos:
        remover_imagem(caminho)
    flash(f"Curso “{titulo}” excluído.", "ok")
    return redirect(url_for("admin.cursos_lista"))
