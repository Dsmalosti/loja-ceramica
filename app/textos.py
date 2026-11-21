"""[back/painel-julia] Textos do site que a Julia edita no painel (Painel > Textos do site).

Cada texto tem um padrão aqui no código. O banco (tabela textos_site) guarda só o que ela mudou;
apagar o campo no painel volta ao padrão. Para deixar um texto novo editável:
1. acrescente um Texto na lista abaixo;
2. no template, troque o texto fixo por {{ texto_site('chave') }} (com o filtro certo).

Formatação permitida (a mesma das descrições de produto): linha em branco = parágrafo,
"- " no começo da linha = lista, **negrito** e *destaque*.
"""
from dataclasses import dataclass

from flask import g


@dataclass(frozen=True)
class Texto:
    chave: str
    grupo: str
    rotulo: str
    padrao: str
    maximo: int
    longo: bool = False  # True = caixa de texto grande (parágrafos)
    ajuda: str = ""


TEXTOS = [
    Texto("slogan", "Marca", "Slogan", "Um espaço para aprender, *criar e viver a cerâmica.*", 120,
          ajuda="Aparece no rodapé, no Sobre nós e na Início. A parte entre *asteriscos* fica em destaque."),

    Texto("inicio_sobre", "Início", "Resumo do ateliê na Início",
          "A Malosti Arte Cerâmica reúne arte, aprendizado, criação e materiais em um só lugar. "
          "Idealizada por Júlia Malosti e Alexandre Malosti, nasceu do amor pela cerâmica.", 400, longo=True),

    Texto("sobre_abertura", "Sobre nós", "Primeiro parágrafo (em destaque)",
          "A Malosti Arte Cerâmica é um espaço dedicado ao universo da cerâmica, reunindo arte, aprendizado, "
          "criação e materiais em um só lugar.", 400, longo=True),
    Texto("sobre_texto", "Sobre nós", "Resto do texto",
          "Idealizada por Júlia Malosti e Alexandre Malosti, a Malosti nasceu do amor pela cerâmica e do desejo de "
          "compartilhar conhecimentos, incentivar a criatividade e aproximar cada vez mais pessoas desse universo.\n\n"
          "Nosso espaço reúne uma escola de cerâmica, com cursos e oficinas, um ambiente dedicado à produção artística "
          "e uma loja especializada em produtos e materiais para ceramistas.\n\n"
          "Mais do que um lugar para aprender ou comprar, queremos ser um ponto de encontro para pessoas que "
          "compartilham o interesse pela cerâmica, promovendo trocas, experiências e novas possibilidades de criação.",
          3000, longo=True, ajuda="Deixe uma linha em branco entre os parágrafos."),

    Texto("personalizadas_titulo", "Serviços: peças personalizadas", "Título", "Peças personalizadas", 80),
    Texto("personalizadas_texto", "Serviços: peças personalizadas", "Texto",
          "Conte o que você imagina (tipo de peça, tamanho, cores, quantidade e prazo) e combinamos tudo pelo WhatsApp.",
          500, longo=True),
    Texto("passo1_titulo", "Serviços: peças personalizadas", "Passo 1: título", "Conte sua ideia", 60),
    Texto("passo1_texto", "Serviços: peças personalizadas", "Passo 1: texto", "Tipo de peça, cores, tamanho e quantidade.", 160),
    Texto("passo2_titulo", "Serviços: peças personalizadas", "Passo 2: título", "Receba o orçamento", 60),
    Texto("passo2_texto", "Serviços: peças personalizadas", "Passo 2: texto", "O ateliê responde com valores e prazo.", 160),
    Texto("passo3_titulo", "Serviços: peças personalizadas", "Passo 3: título", "Peça na sua mesa", 60),
    Texto("passo3_texto", "Serviços: peças personalizadas", "Passo 3: texto", "Feita à mão no ateliê, em 30 a 40 dias.", 160),
]

POR_CHAVE = {texto.chave: texto for texto in TEXTOS}


def grupos():
    """[(grupo, [Texto, ...]), ...] na ordem da lista, para montar o formulário do painel."""
    saida = {}
    for texto in TEXTOS:
        saida.setdefault(texto.grupo, []).append(texto)
    return list(saida.items())


def _mudados():
    # Uma consulta por página, não uma por texto
    if "textos_site" not in g:
        from .models import TextoSite
        g.textos_site = {linha.chave: linha.valor for linha in TextoSite.query.all()}
    return g.textos_site


def texto_site(chave):
    """O texto que vale agora: o que a Julia escreveu ou, se ela não mudou, o padrão."""
    return _mudados().get(chave) or POR_CHAVE[chave].padrao


def salvar(form):
    """Valida e grava o formulário do painel. Devolve a lista de erros (vazia se salvou)."""
    from .extensions import db
    from .models import TextoSite

    erros, novos = [], {}
    for texto in TEXTOS:
        valor = (form.get(texto.chave) or "").replace("\r\n", "\n").strip()
        if len(valor) > texto.maximo:
            erros.append(f"{texto.grupo}, {texto.rotulo}: use no máximo {texto.maximo} caracteres.")
        novos[texto.chave] = valor
    if erros:
        return erros

    atuais = {linha.chave: linha for linha in TextoSite.query.all()}
    for chave, valor in novos.items():
        linha = atuais.get(chave)
        if not valor or valor == POR_CHAVE[chave].padrao:
            if linha:  # vazio ou igual ao original = volta ao padrão
                db.session.delete(linha)
        elif linha:
            linha.valor = valor
        else:
            db.session.add(TextoSite(chave=chave, valor=valor))
    db.session.commit()
    g.pop("textos_site", None)
    return []
