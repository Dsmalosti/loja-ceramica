"""Validação e conversão dos formulários do painel.

Funções puras: não dependem do banco nem do Flask, por isso são fáceis de testar.
Cada validar_* devolve (dados, erros):
  - dados: valores já convertidos e também os textos digitados, para preencher
    o formulário de novo quando houver erro;
  - erros: lista de mensagens em português (vazia se estiver tudo certo).
"""
import re
from decimal import Decimal

PRECO_MAXIMO_CENTAVOS = 100_000_000  # R$ 1.000.000,00
ESTOQUE_MAXIMO = 100_000
TEXTO_LONGO_MAXIMO = 5000


def parse_preco(texto):
    """Converte o que a pessoa digitou em centavos. Devolve None se for inválido.

    '55' -> 5500 | '55,5' -> 5550 | 'R$ 1.234,56' -> 123456 | '55.50' -> 5550
    Padrão brasileiro: ponto com exatamente 3 dígitos depois ('1.500') é separador
    de milhar, ou seja, 1.500 reais.
    """
    if texto is None:
        return None
    t = re.sub(r"\s+", "", str(texto).replace("R$", ""))
    if not t:
        return None
    if "," in t and "." in t:
        t = t.replace(".", "").replace(",", ".")
    elif "," in t:
        t = t.replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", t):
        t = t.replace(".", "")
    if not re.fullmatch(r"\d+(\.\d{1,2})?", t):
        return None
    centavos = int(Decimal(t) * 100)
    if centavos > PRECO_MAXIMO_CENTAVOS:
        return None
    return centavos


def formatar_preco_input(centavos):
    """123456 -> '1234,56' (sem separador de milhar, para reenviar no formulário)."""
    if centavos is None:
        return ""
    reais, cent = divmod(int(centavos), 100)
    return f"{reais},{cent:02d}"


def parse_inteiro(texto, maximo=ESTOQUE_MAXIMO):
    """'12' -> 12. Devolve None se não for um número inteiro de 0 até o máximo."""
    t = str(texto or "").strip()
    if not re.fullmatch(r"\d{1,9}", t):
        return None
    valor = int(t)
    return valor if valor <= maximo else None


def escapar_like(texto):
    """Para usar em ilike(..., escape='\\'): trata % e _ digitados como texto comum."""
    return texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _texto(form, campo):
    return (form.get(campo) or "").strip()


def _checkbox(form, campo):
    return form.get(campo) == "on"


def _validar_tamanho(erros, valor, limite, rotulo):
    if len(valor) > limite:
        erros.append(f"{rotulo}: use no máximo {limite} caracteres.")


def validar_categoria(form):
    erros = []
    nome = _texto(form, "nome")
    if not nome:
        erros.append("Informe o nome da categoria.")
    _validar_tamanho(erros, nome, 80, "Nome")
    return {"nome": nome, "ativa": _checkbox(form, "ativa")}, erros


def validar_produto(form):
    erros = []
    nome = _texto(form, "nome")
    descricao = _texto(form, "descricao")
    preco_texto = _texto(form, "preco")
    estoque_texto = _texto(form, "estoque")
    categoria_texto = _texto(form, "categoria_id")

    if not nome:
        erros.append("Informe o nome do produto.")
    _validar_tamanho(erros, nome, 150, "Nome")
    _validar_tamanho(erros, descricao, TEXTO_LONGO_MAXIMO, "Descrição")

    preco_centavos = parse_preco(preco_texto)
    if preco_centavos is None:
        erros.append("Informe um preço válido, por exemplo 55,00.")
    elif preco_centavos == 0:
        erros.append("O preço precisa ser maior que zero.")

    estoque = parse_inteiro(estoque_texto)
    if estoque is None:
        erros.append("Informe o estoque com um número inteiro (use 0 se acabou).")

    categoria_id = int(categoria_texto) if re.fullmatch(r"\d{1,9}", categoria_texto) else None
    if categoria_id is None:
        erros.append("Escolha uma categoria.")

    dados = {
        "nome": nome,
        "descricao": descricao,
        "preco_texto": preco_texto,
        "preco_centavos": preco_centavos,
        "estoque_texto": estoque_texto,
        "estoque": estoque,
        "categoria_id": categoria_texto,
        "categoria_id_int": categoria_id,
        "ativo": _checkbox(form, "ativo"),
    }
    return dados, erros


def validar_curso(form):
    erros = []
    titulo = _texto(form, "titulo")
    descricao = _texto(form, "descricao")
    duracao = _texto(form, "duracao")
    valor_texto = _texto(form, "valor")

    if not titulo:
        erros.append("Informe o título do curso.")
    _validar_tamanho(erros, titulo, 150, "Título")
    _validar_tamanho(erros, descricao, TEXTO_LONGO_MAXIMO, "Descrição")
    _validar_tamanho(erros, duracao, 80, "Duração")

    # Valor é opcional: vazio significa "sob consulta"
    valor_centavos = None
    if valor_texto:
        valor_centavos = parse_preco(valor_texto)
        if valor_centavos is None:
            erros.append("Valor inválido. Use, por exemplo, 250,00 ou deixe em branco para 'sob consulta'.")

    dados = {
        "titulo": titulo,
        "descricao": descricao,
        "duracao": duracao,
        "valor_texto": valor_texto,
        "valor_centavos": valor_centavos,
        "ativo": _checkbox(form, "ativo"),
    }
    return dados, erros


def validar_servico(form):
    erros = []
    titulo = _texto(form, "titulo")
    descricao = _texto(form, "descricao")

    if not titulo:
        erros.append("Informe o título do serviço.")
    _validar_tamanho(erros, titulo, 150, "Título")
    _validar_tamanho(erros, descricao, TEXTO_LONGO_MAXIMO, "Descrição")

    return {"titulo": titulo, "descricao": descricao, "ativo": _checkbox(form, "ativo")}, erros
