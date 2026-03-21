from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.conversa import Conversa


class ConversaRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_active(
        self,
        *,
        tenant_id: int,
        telefone: str,
        ativa_nos_ultimos_minutos: int | None = None,
    ) -> Conversa | None:
        query = self.db.query(Conversa).filter(
            Conversa.tenant_id == tenant_id,
            Conversa.telefone == telefone,
            Conversa.ativa.is_(True),
        )
        if ativa_nos_ultimos_minutos is not None:
            limite = datetime.utcnow() - timedelta(minutes=ativa_nos_ultimos_minutos)
            query = query.filter(Conversa.atualizado_em >= limite)
        return query.first()

    def upsert(
        self,
        *,
        tenant_id: int,
        telefone: str,
        estado: str,
        contexto: dict | None,
        ativa: bool,
    ) -> Conversa:
        conversa = (
            self.db.query(Conversa)
            .filter(Conversa.tenant_id == tenant_id, Conversa.telefone == telefone)
            .first()
        )
        if not conversa:
            conversa = Conversa(
                tenant_id=tenant_id,
                telefone=telefone,
                estado=estado,
                contexto=contexto,
                ativa=ativa,
            )
            self.db.add(conversa)
            self.db.commit()
            self.db.refresh(conversa)
            return conversa

        conversa.estado = estado
        conversa.contexto = contexto
        conversa.ativa = ativa
        conversa.atualizado_em = datetime.now(timezone.utc).replace(tzinfo=None)
        self.db.commit()
        self.db.refresh(conversa)
        return conversa
