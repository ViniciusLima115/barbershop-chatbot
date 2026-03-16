import BookingTokenActionCard from "@/app/components/BookingTokenActionCard";

export default async function ConfirmarAgendamentoPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  return <BookingTokenActionCard token={token} mode="confirmar" />;
}
