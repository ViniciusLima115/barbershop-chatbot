"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

import { getPublicPaymentStatus, PublicPaymentStatusResponse } from "@/services/api";

type Variant = "sucesso" | "pendente" | "falha";

const TITLES: Record<Variant, string> = {
  sucesso: "Pagamento recebido",
  pendente: "Pagamento em processamento",
  falha: "Pagamento nao concluido",
};

const DESCRIPTIONS: Record<Variant, string> = {
  sucesso: "Recebemos seu retorno do checkout. A confirmacao final do agendamento ocorre pelo webhook oficial do Mercado Pago.",
  pendente: "Seu pagamento ainda esta em analise. A confirmacao final do agendamento ocorre somente quando o webhook for aprovado.",
  falha: "Nao houve confirmacao do pagamento. O agendamento nao sera confirmado como pago sem aprovacao oficial do webhook.",
};

function formatCurrency(value: number) {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  }).format(value);
}

export function PaymentReturnClient({ variant }: { variant: Variant }) {
  const searchParams = useSearchParams();
  const externalReference = searchParams.get("external_reference") || "";

  const [status, setStatus] = useState<PublicPaymentStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;

    async function loadStatus() {
      if (!externalReference) {
        if (!mounted) return;
        setLoading(false);
        setError("Referencia de pagamento nao encontrada no retorno.");
        return;
      }

      try {
        const result = await getPublicPaymentStatus(externalReference);
        if (!mounted) return;
        setStatus(result);
      } catch (err) {
        if (!mounted) return;
        setError(err instanceof Error ? err.message : "Falha ao consultar status do pagamento.");
      } finally {
        if (mounted) setLoading(false);
      }
    }

    loadStatus();

    if (variant !== "sucesso") return () => { mounted = false; };

    const intervalId = window.setInterval(loadStatus, 5000);
    return () => {
      mounted = false;
      window.clearInterval(intervalId);
    };
  }, [externalReference, variant]);

  return (
    <main className="min-h-screen bg-slate-100 px-4 py-10">
      <div className="mx-auto max-w-xl rounded-2xl bg-white p-6 shadow">
        <h1 className="text-2xl font-bold text-slate-900">{TITLES[variant]}</h1>
        <p className="mt-2 text-sm text-slate-600">{DESCRIPTIONS[variant]}</p>

        {!externalReference && (
          <p className="mt-4 rounded-lg bg-amber-100 px-3 py-2 text-sm text-amber-900">
            Sem referencia de pagamento no retorno.
          </p>
        )}

        {loading && <p className="mt-4 text-sm text-slate-600">Consultando status...</p>}

        {error && (
          <p className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
        )}

        {status && (
          <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">
            <p><strong>Referencia:</strong> {status.external_reference}</p>
            <p><strong>Agendamento:</strong> #{status.agendamento_id}</p>
            <p><strong>Status do pagamento:</strong> {status.pagamento_status}</p>
            <p><strong>Status do agendamento:</strong> {status.agendamento_status}</p>
            <p><strong>Valor:</strong> {formatCurrency(status.amount)}</p>
          </div>
        )}

        <div className="mt-6 flex gap-3">
          <Link href="/" className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-semibold text-white">
            Voltar ao inicio
          </Link>
        </div>
      </div>
    </main>
  );
}
