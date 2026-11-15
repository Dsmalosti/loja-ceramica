"""Servidor de DEMONSTRAÇÃO no computador, com o pagamento do Mercado Pago SIMULADO.

Não faz parte do site publicado: serve só pra testar a loja inteira no computador (e no
celular, na mesma rede Wi-Fi) sem as chaves do Mercado Pago. O Mercado Pago de verdade não
aceita "localhost" nas URLs de volta, então aqui o "pagamento" leva direto à tela de retorno
como aprovado, e a tela confirma com este Mercado Pago falso. Todo o resto é o código real.

Uso (na raiz do projeto, com o venv ativo e o banco preparado: flask db upgrade && flask seed-demo):
    python scripts/servidor_demo.py          # só neste computador: http://localhost:5000
    python scripts/servidor_demo.py --rede   # também no celular: http://<ip-do-computador>:5000

Recusa rodar com APP_ENV=production.
"""
import itertools
import os
import socket
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

PORTA = 5000


def ip_na_rede():
    """IP deste computador na rede local (nenhum dado é enviado: o UDP só escolhe a placa de rede)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("10.255.255.255", 1))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def main():
    na_rede = "--rede" in sys.argv
    from app import create_app  # noqa: E402  (depois do sys.path)
    from app.extensions import db
    from app.models import Pedido
    from app.services import mercadopago

    app = create_app("development")
    if app.config["APP_ENV"] == "production" or os.environ.get("APP_ENV") == "production":
        sys.exit("Recusado: o servidor de demo simula pagamentos e não roda em produção.")

    base = f"http://{ip_na_rede() if na_rede else 'localhost'}:{PORTA}"
    # IDs únicos entre reinícios (como no Mercado Pago real), senão a trava de idempotência
    # reconhece um ID de uma rodada anterior e, corretamente, não processa de novo.
    contador = itertools.count(int(time.time() * 1000))
    pagamentos = {}

    def mercado_pago_simulado(metodo, caminho, corpo=None, idempotencia=None):
        if caminho == "/checkout/preferences":
            ref, pid = corpo["external_reference"], str(next(contador))
            pagamentos[pid] = ref
            return {"id": f"pref-demo-{ref}",
                    "init_point": f"{base}/checkout/retorno/{ref}?payment_id={pid}&status=approved"}
        if caminho.startswith("/v1/payments/"):
            pid = caminho.rsplit("/", 1)[1]
            if pid not in pagamentos:
                raise mercadopago.ErroMercadoPago("pagamento desconhecido")
            pedido = db.session.get(Pedido, int(pagamentos[pid]))
            return {"id": int(pid), "status": "approved", "external_reference": str(pedido.id),
                    "transaction_amount": pedido.total_centavos / 100, "currency_id": "BRL"}
        raise mercadopago.ErroMercadoPago("chamada inesperada")

    app.config.update(MP_ACCESS_TOKEN="DEMO-simulado", SITE_URL=base, MP_WEBHOOK_SECRET="demo-simulado")
    mercadopago._requisicao = mercado_pago_simulado

    print(f"Loja de DEMONSTRAÇÃO (pagamento simulado) em {base}")
    if na_rede:
        print("No celular, conectado na mesma rede Wi-Fi, abra o endereço acima.")
        print("Se o Windows perguntar, permita o acesso do Python em 'Redes privadas'.")
    app.run(host="0.0.0.0" if na_rede else "127.0.0.1", port=PORTA, debug=False)


if __name__ == "__main__":
    main()
