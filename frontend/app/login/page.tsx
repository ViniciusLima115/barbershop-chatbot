"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { Eye, Headset, Laptop, MessageCircle, User, X } from "lucide-react";
import { login, fetchMe } from "@/services/auth";
import { loginUsuario } from "@/services/api";
import styles from "./page.module.css";

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

    if (!usuario || !senha) {
      setError("Preencha todos os campos para entrar.");
      return;
    }

    setLoading(true);

    try {
      const resposta = await loginUsuario({
        usuario,
        senha,
      });

      if (resposta.is_admin) {
        login({
          email: usuario,
          tenantId: "admin",
          tenantName: "Administrador",
          plan: "premium",
          accessToken: resposta.access_token,
        });
        router.replace("/");
        return;
      }

      if (!resposta.tenant_id || !resposta.tenant_name) {
        setError("Nao foi possivel identificar o estabelecimento do usuario.");
        return;
      }

      const me = await fetchMe(resposta.access_token);
      login({
        email: usuario,
        tenantId: String(resposta.tenant_id),
        tenantName: resposta.tenant_name,
        plan: resposta.plano === "premium" ? "premium" : "basico",
        accessToken: resposta.access_token,
        accentColor: me?.accent_color,
        bgColor: me?.bg_color,
        logoUrl: me?.logo_url,
      });

      router.replace("/");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Nao foi possivel iniciar sessao.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className={styles.page}>
      {/* PAINEL ESQUERDO — branding */}
      <div className={styles.left}>
        <div className={styles.leftBrand}>
          <div className={styles.leftIcon}>
            {/* Laptop já é o ícone usado no login atual — mantido por consistência */}
            <Laptop size={18} color="white" />
          </div>
          <div>
            <div className={styles.leftEyebrow}>Sistema de gestão</div>
            <div className={styles.leftBrandName}>VirtualBarber</div>
          </div>
        </div>

        <div className={styles.leftCopy}>
          <h1 className={styles.leftTitle}>Seu negócio,<br />bem gerido.</h1>
          <div className={styles.leftDivider} />
          <div className={styles.socialProof}>
            <div className={styles.avatars}>
              <div className={styles.avatar}>CA</div>
              <div className={styles.avatar}>MB</div>
              <div className={styles.avatar}>+</div>
            </div>
            <div className={styles.socialText}>
              <strong>+50 estabelecimentos</strong><br />já usam o sistema
            </div>
          </div>
        </div>
      </div>

      {/* PAINEL DIREITO — formulário */}
      <div className={styles.right}>
        <p className={styles.formEyebrow}>Área restrita</p>
        <h2 className={styles.formTitle}>Bem-vindo<br />de volta.</h2>
        <p className={styles.formSub}>Acesse o painel do seu estabelecimento.</p>

        <form onSubmit={handleSubmit} className={styles.form}>
          <div className={styles.field}>
            <label htmlFor="email" className={styles.label}>Usuário</label>
            <div className={styles.inputWrap}>
              <input
                id="email"
                type="text"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className={styles.input}
                placeholder="Digite seu usuário"
                autoComplete="username"
              />
              <User size={16} className={styles.inputIcon} />
            </div>
          </div>

          <div className={styles.field}>
            <label htmlFor="password" className={styles.label}>Senha</label>
            <div className={styles.inputWrap}>
              <input
                id="password"
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className={styles.input}
                placeholder="Digite sua senha"
                autoComplete="current-password"
              />
              <button
                type="button"
                onClick={() => setShowPassword((prev) => !prev)}
                className={styles.ghostButton}
                aria-label={showPassword ? "Ocultar senha" : "Mostrar senha"}
              >
                <Eye size={16} />
              </button>
            </div>
          </div>

          {error && <div className={styles.error}>{error}</div>}

          <button
            type="submit"
            className={styles.submit}
            disabled={loading}
          >
            {loading ? "Entrando..." : "Entrar"}
          </button>
        </form>

        <button
          type="button"
          onClick={() => setShowSupportCard(true)}
          className={styles.supportLink}
        >
          Esqueceu a senha? Fale com o suporte
        </button>
      </div>

      {/* SUPPORT CARD OVERLAY */}
      {showSupportCard && (
        <div className={styles.overlay}>
          <div className={styles.supportCard}>
            <div className={styles.supportHeader}>
              <div className={styles.supportIntro}>
                <span className={styles.supportIcon}>
                  <Headset size={18} />
                </span>
                <div>
                  <p className={styles.supportTitle}>Contate o suporte</p>
                  <p className={styles.supportSub}>Recuperação de acesso</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setShowSupportCard(false)}
                className="icon-button"
                aria-label="Fechar card de suporte"
              >
                <X size={16} />
              </button>
            </div>
            <p className={styles.supportText}>
              Para recuperar sua senha, fale com nosso atendimento.
            </p>
            <div className={styles.supportActions}>
              <a
                href="https://wa.me/5582999627481"
                target="_blank"
                rel="noreferrer"
                className={styles.whatsButton}
              >
                <MessageCircle size={16} />
                Falar no WhatsApp
              </a>
              <button
                type="button"
                onClick={() => setShowSupportCard(false)}
                className={styles.closeButton}
              >
                Fechar
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
