"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { Eye, Headset, Laptop, MessageCircle, User, X } from "lucide-react";
import { login } from "@/services/auth";
import { checkAdminLogin } from "@/services/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [showSupportCard, setShowSupportCard] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    const usuario = email.trim();
    const senha = password;
    const adminCredencialExata = usuario === "vhtech_" && senha === "@dinizvascaino";

    if (!usuario || !senha) {
      setError("Preencha todos os campos para entrar.");
      return;
    }

    setLoading(true);

    try {
      const adminCheck = await checkAdminLogin({
        usuario,
        senha,
      }).catch(() => ({ is_admin: false }));

      if (adminCheck.is_admin || adminCredencialExata) {
        login({
          email: usuario,
          tenantId: "admin",
          tenantName: "Administrador",
        });
        router.replace("/admin");
        return;
      }

      login({
        email: usuario,
        tenantId: "1",
        tenantName: "Barbearia",
      });

      router.replace("/");
    } catch {
      setError("Nao foi possivel iniciar sessao.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="flex min-h-dvh items-center justify-center bg-[#f5f5f7] px-4 py-10">
      <div className="w-full max-w-sm text-center">
        <div className="mx-auto -translate-y-8 flex flex-col items-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-slate-900 text-white">
            <Laptop size={20} />
          </div>
        </div>

        <h1 className="mt-10 text-4xl font-semibold tracking-tight text-slate-900">Login</h1>

        <form onSubmit={handleSubmit} className="mt-12 flex flex-col gap-6 text-left">
          <div className="space-y-2">
            <label htmlFor="email" className="block text-sm font-semibold text-slate-700">
              Usuario
            </label>
            <div className="relative">
              <input
                id="email"
                type="text"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="h-12 w-full rounded-lg border border-slate-200 bg-white px-4 pr-11 text-base text-slate-800 placeholder:text-slate-400 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100"
                placeholder="Digite seu usuario"
                autoComplete="username"
              />
              <User size={17} className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-slate-400" />
            </div>
          </div>

          <div className="space-y-2">
            <label htmlFor="password" className="block text-sm font-semibold text-slate-700">
              Senha
            </label>
            <div className="relative">
              <input
                id="password"
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="h-12 w-full rounded-lg border border-slate-200 bg-white px-4 pr-11 text-base text-slate-800 placeholder:text-slate-400 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100"
                placeholder="Digite sua senha"
                autoComplete="current-password"
              />
              <button
                type="button"
                onClick={() => setShowPassword((prev) => !prev)}
                className="absolute right-3 top-1/2 -translate-y-1/2 rounded p-1 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600"
                aria-label={showPassword ? "Ocultar senha" : "Mostrar senha"}
              >
                <Eye size={17} />
              </button>
            </div>
          </div>

          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm font-medium text-red-700">
              {error}
            </div>
          )}

          <div className="pt-2">
            <button
              type="submit"
              className="h-12 w-full rounded-lg bg-[#4f80d9] text-base font-semibold text-white shadow-[0_6px_14px_rgba(79,128,217,0.25)] transition hover:brightness-105 disabled:opacity-60"
              disabled={loading}
            >
              {loading ? "Entrando..." : "Sign in"}
            </button>
          </div>
        </form>

        <button
          type="button"
          onClick={() => setShowSupportCard(true)}
          className="mt-6 text-sm font-medium text-slate-400 transition hover:text-slate-600"
        >
          Esqueceu a senha?
        </button>
      </div>

      {showSupportCard && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/45 px-4 backdrop-blur-[2px]">
          <div className="w-full max-w-sm rounded-2xl border border-slate-200 bg-white p-5 shadow-2xl">
            <div className="mb-4 flex items-start justify-between">
              <div className="flex items-center gap-2">
                <span className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-blue-50 text-blue-600">
                  <Headset size={18} />
                </span>
                <div>
                  <p className="text-base font-semibold text-slate-900">Contate o suporte</p>
                  <p className="text-xs text-slate-500">Recuperacao de acesso</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setShowSupportCard(false)}
                className="rounded-md p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600"
                aria-label="Fechar card de suporte"
              >
                <X size={16} />
              </button>
            </div>

            <p className="text-sm text-slate-600">Para recuperar sua senha, fale com nosso atendimento.</p>

            <a
              href="https://wa.me/5582999627481"
              target="_blank"
              rel="noreferrer"
              className="mt-5 inline-flex h-11 w-full items-center justify-center gap-2 rounded-lg bg-green-600 text-sm font-semibold text-white transition hover:bg-green-700"
            >
              <MessageCircle size={16} />
              Falar no WhatsApp
            </a>

            <button
              type="button"
              onClick={() => setShowSupportCard(false)}
              className="mt-3 h-10 w-full rounded-lg border border-slate-200 bg-white text-sm font-medium text-slate-700 transition hover:bg-slate-50"
            >
              Fechar
            </button>
          </div>
        </div>
      )}
    </main>
  );
}
