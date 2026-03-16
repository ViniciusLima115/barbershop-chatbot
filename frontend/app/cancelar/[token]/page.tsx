import BookingTokenActionCard from "@/app/components/BookingTokenActionCard";

export default async function CancelarAgendamentoPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  return <BookingTokenActionCard token={token} mode="cancelar" />;
}
