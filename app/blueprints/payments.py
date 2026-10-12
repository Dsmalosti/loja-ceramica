from flask import Blueprint

# Checkout e webhook do Mercado Pago entram aqui (etapa de pagamento).
bp = Blueprint("payments", __name__, url_prefix="/pagamento")
