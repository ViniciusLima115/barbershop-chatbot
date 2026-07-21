from datetime import date, datetime, time, timedelta

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models.agendamento import Agendamento
from app.models.barbeiro import Barbeiro
from app.models.cliente import Cliente
from app.models.servico import Servico
from app.time_utils import utcnow_naive


class BookingRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_public_barbeiros(self, tenant_id: int, only_active: bool = True) -> list[Barbeiro]:
        query = self.db.query(Barbeiro).filter(Barbeiro.estabelecimento_id == tenant_id)
        if only_active:
            query = query.filter(Barbeiro.ativo.is_(True))
        return query.order_by(Barbeiro.id.asc()).all()

    def list_public_servicos(self, tenant_id: int) -> list[Servico]:
        return (
            self.db.query(Servico)
            .filter(Servico.estabelecimento_id == tenant_id)
            .order_by(Servico.id.asc())
            .all()
        )

    def get_barbeiro(
        self,
        tenant_id: int,
        barbeiro_id: int,
        only_active: bool = True,
        for_update: bool = False,
    ) -> Barbeiro | None:
        query = self.db.query(Barbeiro).filter(
            Barbeiro.id == barbeiro_id,
            Barbeiro.estabelecimento_id == tenant_id,
        )
        if only_active:
            query = query.filter(Barbeiro.ativo.is_(True))
        if for_update:
            query = query.with_for_update()
        return query.first()

    def get_servico(self, tenant_id: int, servico_id: int) -> Servico | None:
        return (
            self.db.query(Servico)
            .filter(
                Servico.id == servico_id,
                Servico.estabelecimento_id == tenant_id,
            )
            .first()
        )

    def get_cliente_by_telefone(self, *, tenant_id: int, telefone: str) -> Cliente | None:
        return (
            self.db.query(Cliente)
            .filter(
                Cliente.telefone == telefone,
                Cliente.estabelecimento_id == tenant_id,
            )
            .first()
        )

    def get_or_create_cliente(
        self,
        *,
        tenant_id: int,
        telefone: str,
        nome: str,
        email: str | None = None,
    ) -> Cliente:
        cliente = (
            self.db.query(Cliente)
            .filter(
                Cliente.telefone == telefone,
                Cliente.estabelecimento_id == tenant_id,
            )
            .first()
        )
        if cliente:
            if nome and cliente.nome in ("Cliente", "", None):
                cliente.nome = nome
            if email and not cliente.email:
                cliente.email = email
            return cliente

        cliente = Cliente(
            nome=nome,
            telefone=telefone,
            email=email,
            etapa_atual="menu",
            estabelecimento_id=tenant_id,
        )
        self.db.add(cliente)
        self.db.flush()
        return cliente

    def get_conflicting_agendamento(
        self,
        *,
        tenant_id: int,
        barbeiro_id: int,
        inicio: datetime,
        fim: datetime,
    ) -> Agendamento | None:
        now = utcnow_naive()
        return (
            self.db.query(Agendamento)
            .filter(
                Agendamento.barbeiro_id == barbeiro_id,
                Agendamento.estabelecimento_id == tenant_id,
                or_(
                    Agendamento.status.in_(["pendente", "confirmado", "reagendamento_solicitado"]),
                    and_(
                        Agendamento.status == "pending_payment",
                        or_(
                            Agendamento.payment_hold_expires_at.is_(None),
                            Agendamento.payment_hold_expires_at > now,
                        ),
                    ),
                ),
                Agendamento.data_hora_inicio < fim,
                Agendamento.data_hora_fim > inicio,
            )
            .first()
        )

    def create_agendamento(
        self,
        *,
        tenant_id: int,
        cliente_id: int,
        cliente_nome: str,
        cliente_telefone: str,
        cliente_email: str | None = None,
        barbeiro_id: int,
        servico_id: int,
        inicio: datetime,
        fim: datetime,
        status: str = "pendente",
        pagamento_adiantado_exigido: bool = False,
    ) -> Agendamento:
        agendamento = Agendamento(
            tenant_id=tenant_id,
            cliente_id=cliente_id,
            cliente_nome=cliente_nome,
            cliente_telefone=cliente_telefone,
            cliente_email=cliente_email,
            barbeiro_id=barbeiro_id,
            servico_id=servico_id,
            data=inicio.date(),
            hora_inicio=inicio.time().replace(second=0, microsecond=0),
            data_hora_inicio=inicio,
            data_hora_fim=fim,
            status=status,
            pagamento_adiantado_exigido=pagamento_adiantado_exigido,
            confirmation_token_expires_at=fim + timedelta(days=1),
        )
        self.db.add(agendamento)
        self.db.flush()
        return agendamento

    def list_agendamentos(
        self,
        *,
        tenant_id: int,
        data_filtro: date | None = None,
        barbeiro_id: int | None = None,
    ) -> list[Agendamento]:
        query = self.db.query(Agendamento).filter(Agendamento.estabelecimento_id == tenant_id)
        if data_filtro:
            inicio = datetime.combine(data_filtro, time(0, 0))
            fim = inicio + timedelta(days=1)
            query = query.filter(
                Agendamento.data_hora_inicio >= inicio,
                Agendamento.data_hora_inicio < fim,
            )
        if barbeiro_id:
            query = query.filter(Agendamento.barbeiro_id == barbeiro_id)

        return query.order_by(Agendamento.data_hora_inicio.asc()).all()
