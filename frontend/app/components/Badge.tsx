interface BadgeProps {
  status: "confirmado" | "pendente" | "cancelado" | "livre" | "ocupado";
  children?: React.ReactNode;
}

export default function Badge({ status, children }: BadgeProps) {
  const statusConfig = {
    confirmado: "badge-success",
    pendente: "badge-pending",
    cancelado: "badge-danger",
    livre: "badge-success",
    ocupado: "badge-pending",
  };

  const statusLabel = {
    confirmado: "Confirmado",
    pendente: "Pendente",
    cancelado: "Cancelado",
    livre: "Livre",
    ocupado: "Ocupado",
  };

  return (
    <span className={`badge ${statusConfig[status]}`}>
      {children || statusLabel[status]}
    </span>
  );
}
