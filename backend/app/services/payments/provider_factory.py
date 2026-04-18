from app.services.payments.constants import PAYMENT_PROVIDER_MERCADO_PAGO
from app.services.payments.providers.base import PaymentProvider
from app.services.payments.providers.mercadopago import MercadoPagoProvider


def get_payment_provider(provider: str) -> PaymentProvider:
    normalized = (provider or "").strip().lower()
    if normalized in {PAYMENT_PROVIDER_MERCADO_PAGO, "mercado_pago"}:
        return MercadoPagoProvider()
    raise ValueError(f"Provider de pagamento nao suportado: {provider}")
