"""[back/painel-julia] Painel > Textos do site: slogan, Sobre nós e peças personalizadas."""
from flask import flash, redirect, render_template, request, url_for

from .. import textos
from .admin import bp


@bp.route("/textos", methods=["GET", "POST"])
def textos_site():
    if request.method == "POST":
        erros = textos.salvar(request.form)
        if not erros:
            flash("Textos salvos. Já estão no site.", "ok")
            return redirect(url_for("admin.textos_site"))
        for erro in erros:
            flash(erro, "erro")
        valores = {t.chave: request.form.get(t.chave, "") for t in textos.TEXTOS}
    else:
        valores = {t.chave: textos.texto_site(t.chave) for t in textos.TEXTOS}
    return render_template("admin/textos.html", grupos=textos.grupos(), valores=valores)
