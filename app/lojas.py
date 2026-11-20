"""As duas lojas do ateliê. Cada categoria pertence a uma delas.

Fica fora de models.py para os validadores continuarem sem depender do banco.
"""
LOJA_PECAS = "pecas"
LOJA_PRODUTOS = "produtos"

LOJAS = {
    LOJA_PECAS: "Peças de cerâmica",
    LOJA_PRODUTOS: "Produtos para cerâmica",
}
