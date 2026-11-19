"""Validação e conversão dos formulários do painel.

Funções puras: não dependem do banco nem do Flask, por isso são fáceis de testar.
Cada validar_* devolve (dados, erros):
  - dados: valores já convertidos e também os textos digitados, para preencher
    o formulário de novo quando houver erro;
  - erros: lista de mensagens em português (vazia se estiver tudo certo).
"""
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from .lojas import LOJA_PECAS, LOJAS

PRECO_MAXIMO_CENTAVOS = 100_000_000  # R$ 1.000.000,00
ESTOQUE_MAXIMO = 100_000
TEXTO_LONGO_MAXIMO = 5000
# [back/compra-por-loja] Embalagem do produto: (campo, rótulo, máximo)
CAMPOS_ENVIO = (
    ("peso_gramas", "Peso", 100_000),
    ("altura_cm", "Altura", 300),
    ("largura_cm", "Largura", 300),
    ("comprimento_cm", "Comprimento", 300),
)


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
    # [back/duas-lojas] Campo novo. Antes devolvia só nome e ativa.
    loja = _texto(form, "loja") or LOJA_PECAS
    if loja not in LOJAS:
        erros.append("Escolha uma das lojas.")
    return {"nome": nome, "ativa": _checkbox(form, "ativa"), "loja": loja}, erros


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
    # [back/compra-por-loja] Campos novos. Vazio é aceito aqui; quem exige é o painel, conforme a loja.
    for campo, rotulo, maximo in CAMPOS_ENVIO:
        texto = _texto(form, campo)
        valor = parse_inteiro(texto, maximo=maximo) if texto else None
        if texto and not valor:
            erros.append(f"{rotulo}: use um número inteiro de 1 até {maximo}.")
        dados[campo] = texto
        dados[f"{campo}_int"] = valor
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


# ---------- Área do cliente ----------

UFS = (
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA",
    "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
)


def validar_telefone(texto):
    """'(12) 99139-9090' -> '12991399090'. Vazio -> ''. Inválido -> None.

    Aceita fixo (10 dígitos) ou celular (11 dígitos), sempre com DDD.
    """
    digitos = re.sub(r"\D", "", str(texto or ""))
    if not digitos:
        return ""
    return digitos if len(digitos) in (10, 11) else None


def validar_endereco(form):
    erros = []
    cep = re.sub(r"\D", "", _texto(form, "cep"))
    dados = {
        "cep": cep,
        "logradouro": _texto(form, "logradouro"),
        "numero": _texto(form, "numero"),
        "complemento": _texto(form, "complemento"),
        "bairro": _texto(form, "bairro"),
        "cidade": _texto(form, "cidade"),
        "uf": _texto(form, "uf").upper(),
    }

    if len(cep) != 8 or not re.fullmatch(r"[\d\-.\s]+", _texto(form, "cep") or "x"):
        erros.append("Informe um CEP com 8 números, por exemplo 12246-000.")
    for campo, rotulo, limite in (("logradouro", "Rua", 150), ("numero", "Número", 20),
                                  ("bairro", "Bairro", 80), ("cidade", "Cidade", 80)):
        if not dados[campo]:
            erros.append(f"Informe: {rotulo}.")
        _validar_tamanho(erros, dados[campo], limite, rotulo)
    _validar_tamanho(erros, dados["complemento"], 80, "Complemento")
    if dados["uf"] not in UFS:
        erros.append("Escolha o estado (UF).")

    return dados, erros


# ---------- Promoções ----------

# Brasília = UTC-3 fixo (sem horário de verão desde 2019). Repetido aqui para as
# validações continuarem puras (sem importar o Flask).
_FUSO_BRASILIA = timezone(timedelta(hours=-3))
PERCENTUAL_MAXIMO = 90


def parse_data_hora(texto):
    """'2026-11-20T23:30' (campo datetime-local, horário de Brasília) -> datetime em UTC. Inválido -> None."""
    try:
        local = datetime.strptime(str(texto or "").strip(), "%Y-%m-%dT%H:%M")
    except ValueError:
        return None
    return local.replace(tzinfo=_FUSO_BRASILIA).astimezone(timezone.utc)


def formatar_data_hora_input(momento):
    """datetime (UTC) -> '2026-11-20T23:30' no horário de Brasília, para o campo datetime-local."""
    if momento is None:
        return ""
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=timezone.utc)
    return momento.astimezone(_FUSO_BRASILIA).strftime("%Y-%m-%dT%H:%M")


def _ids(form, campo):
    ids = []
    for texto in form.getlist(campo):
        valor = parse_inteiro(texto, maximo=10**9)
        ids.append(valor if valor else -1)  # -1 = inválido (vira erro abaixo)
    return sorted(set(ids))


def validar_promocao(form, precos_produtos, precos_cursos):
    """precos_produtos/precos_cursos: {id: preço em centavos (curso pode ser None)} do que existe no banco."""
    erros = []
    nome = _texto(form, "nome")
    tipo = _texto(form, "tipo")
    percentual_texto = _texto(form, "percentual")
    valor_texto = _texto(form, "valor")
    inicio_texto, fim_texto = _texto(form, "inicio"), _texto(form, "fim")
    produto_ids, curso_ids = _ids(form, "produtos"), _ids(form, "cursos")

    if not nome:
        erros.append("Dê um nome para a promoção (ex.: Semana das canecas).")
    _validar_tamanho(erros, nome, 80, "Nome")

    percentual = valor_centavos = None
    if tipo == "percentual":
        percentual = parse_inteiro(percentual_texto, maximo=PERCENTUAL_MAXIMO)
        if not percentual:
            erros.append(f"Desconto em %: use um número de 1 a {PERCENTUAL_MAXIMO}.")
            percentual = None
    elif tipo == "valor":
        valor_centavos = parse_preco(valor_texto)
        if not valor_centavos:
            erros.append("Informe o valor do desconto, por exemplo 10,00.")
            valor_centavos = None
    else:
        erros.append("Escolha o tipo de desconto: percentual ou valor fixo.")

    inicio, fim = parse_data_hora(inicio_texto), parse_data_hora(fim_texto)
    if inicio is None or fim is None:
        erros.append("Informe a data e a hora de início e de fim.")
    elif fim <= inicio:
        erros.append("O fim da promoção precisa ser depois do início.")

    if not produto_ids and not curso_ids:
        erros.append("Marque pelo menos uma peça ou um curso.")
    if any(pid not in precos_produtos for pid in produto_ids):
        erros.append("Alguma peça marcada não existe mais. Recarregue a página.")
    if any(cid not in precos_cursos for cid in curso_ids):
        erros.append("Algum curso marcado não existe mais. Recarregue a página.")
    elif any(precos_cursos[cid] is None for cid in curso_ids):
        erros.append("Curso com valor sob consulta não pode entrar em promoção.")

    if valor_centavos:
        precos = [precos_produtos[p] for p in produto_ids if p in precos_produtos]
        precos += [precos_cursos[c] for c in curso_ids if precos_cursos.get(c) is not None]
        if precos and valor_centavos >= min(precos):
            erros.append("O desconto em reais precisa ser menor que o preço de todos os itens marcados.")

    return {
        "nome": nome, "tipo": tipo, "percentual": percentual, "valor_centavos": valor_centavos,
        "percentual_texto": percentual_texto, "valor_texto": valor_texto,
        "inicio": inicio, "fim": fim, "inicio_texto": inicio_texto, "fim_texto": fim_texto,
        "produto_ids": [p for p in produto_ids if p > 0], "curso_ids": [c for c in curso_ids if c > 0],
        "ativa": _checkbox(form, "ativa"),
    }, erros
