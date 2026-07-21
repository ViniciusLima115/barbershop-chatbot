"use client";

import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { lookupPublicEstabelecimentoById } from "@/services/api";

export default function RedirectToSlugPage() {
  const params = useParams<{ estabelecimentoId: string }>();
  const router = useRouter();

  useEffect(() => {
    const id = Number(params?.estabelecimentoId);
    if (!Number.isFinite(id)) {
      router.replace("/");
      return;
    }
    lookupPublicEstabelecimentoById({ estabelecimento_id: id })
      .then((data) => router.replace(`/${data.slug}`))
      .catch(() => router.replace("/"));
  }, [params, router]);

  return (
    <main className="flex min-h-screen items-center justify-center bg-zinc-900">
      <p className="text-sm text-zinc-400">Redirecionando...</p>
    </main>
  );
}
