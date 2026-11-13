from ..utils import slugify


def slug_unico(modelo, texto, ignorar_id=None):
    """Gera um slug que ainda não existe na tabela: 'caneca' -> 'caneca-2' se já houver."""
    base = (slugify(texto) or "item")[:100]
    slug, numero = base, 2
    while True:
        consulta = modelo.query.filter_by(slug=slug)
        if ignorar_id is not None:
            consulta = consulta.filter(modelo.id != ignorar_id)
        if consulta.first() is None:
            return slug
        slug = f"{base}-{numero}"
        numero += 1
