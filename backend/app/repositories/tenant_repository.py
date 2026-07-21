from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.estabelecimento import Estabelecimento


class TenantRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, tenant_id: int) -> Estabelecimento | None:
        return self.db.query(Estabelecimento).filter(Estabelecimento.id == tenant_id).first()

    def get_by_slug(self, slug: str) -> Estabelecimento | None:
        return self.db.query(Estabelecimento).filter(Estabelecimento.slug == slug.strip().lower()).first()

    def resolve_by_instance_or_whatsapp(
        self,
        *,
        instance_key: str | None = None,
        whatsapp_number: str | None = None,
    ) -> Estabelecimento | None:
        if instance_key:
            by_instance = (
                self.db.query(Estabelecimento)
                .filter(Estabelecimento.mega_instance_key == instance_key.strip())
                .first()
            )
            if by_instance:
                return by_instance

        if not whatsapp_number:
            return None

        numero_bruto = whatsapp_number.strip()
        numero_normalizado = "".join(ch for ch in numero_bruto if ch.isdigit())
        filtros = [Estabelecimento.whatsapp_number == numero_bruto]
        if numero_normalizado and numero_normalizado != numero_bruto:
            filtros.append(Estabelecimento.whatsapp_number == numero_normalizado)

        return self.db.query(Estabelecimento).filter(or_(*filtros)).first()
