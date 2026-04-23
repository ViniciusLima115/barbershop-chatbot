"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Settings, User, Lock, Palette, Bell, ArrowLeft } from "lucide-react";

import { useAuthSession, AUTH_STORAGE_KEY } from "@/services/auth";
import { API_URL } from "@/services/api";
import styles from "./page.module.css";

type Section = "perfil" | "senha" | "tema" | "notificacoes";

const SECTIONS: { id: Section; label: string; icon: React.ElementType }[] = [
  { id: "perfil", label: "Perfil", icon: User },
  { id: "senha", label: "Senha", icon: Lock },
  { id: "tema", label: "Tema", icon: Palette },
  { id: "notificacoes", label: "Notificacoes", icon: Bell },
];

type Preset = {
  label: string;
  accent: string;
  bg: string;
};

const PRESETS: Preset[] = [
  { label: "Indigo", accent: "#4f46e5", bg: "#ffffff" },
  { label: "Teal", accent: "#0d9488", bg: "#ffffff" },
  { label: "Rosa", accent: "#db2777", bg: "#ffffff" },
  { label: "Ambar", accent: "#d4930a", bg: "#ffffff" },
  { label: "Ardosia", accent: "#475569", bg: "#f8fafc" },
  { label: "Coral", accent: "#e2522b", bg: "#fffaf8" },
  { label: "Noturno", accent: "#e5a820", bg: "#0f0f0e" },
];

async function patchConfiguracao(
  section: string,
  body: Record<string, unknown>,
  token: string,
): Promise<{ ok: boolean; detail?: string }> {
  try {
    const resp = await fetch(`${API_URL}/configuracoes/${section}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(body),
    });
    const data = await resp.json().catch(() => ({}));
    return { ok: resp.ok, detail: data.detail };
  } catch {
    return { ok: false, detail: "Erro de conexao." };
  }
}

export default function ConfiguracoesPage() {
  const session = useAuthSession();
  const router = useRouter();
  const searchParams = useSearchParams();

  const [activeSection, setActiveSection] = useState<Section>("perfil");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [nome, setNome] = useState(session?.tenantName ?? "");
  const [endereco, setEndereco] = useState("");
  const [whatsapp, setWhatsapp] = useState("");
  const [slug, setSlug] = useState("");

  const [senhaAtual, setSenhaAtual] = useState("");
  const [novaSenha, setNovaSenha] = useState("");
  const [confirmarSenha, setConfirmarSenha] = useState("");

  const [accentColor, setAccentColor] = useState(session?.accentColor ?? "#4f46e5");
  const [bgColor, setBgColor] = useState(session?.bgColor ?? "#ffffff");
  const [logoUrl, setLogoUrl] = useState(session?.logoUrl ?? "");
  const [activePreset, setActivePreset] = useState<string | null>(null);

  const [notifAtivo, setNotifAtivo] = useState(true);
  const [notifHoras, setNotifHoras] = useState<number>(2);

  useEffect(() => {
    if (session?.tenantId === "admin") router.replace("/admin");
  }, [session?.tenantId, router]);

  useEffect(() => {
    const aba = searchParams.get("aba");
    if (aba === "perfil" || aba === "senha" || aba === "tema" || aba === "notificacoes") {
      setActiveSection(aba);
    }
  }, [searchParams]);

  function clearMessages() {
    setSuccess(null);
    setError(null);
  }

  function applyPreset(preset: Preset) {
    setAccentColor(preset.accent);
    setBgColor(preset.bg);
    setActivePreset(preset.label);
    document.documentElement.style.setProperty("--accent", preset.accent);
  }

  async function handleSalvarPerfil(e: React.FormEvent) {
    e.preventDefault();
    if (!session?.accessToken) return;
    clearMessages();
    setLoading(true);
    const result = await patchConfiguracao(
      "perfil",
      {
        nome: nome || undefined,
        endereco: endereco || undefined,
        whatsapp_number: whatsapp || undefined,
        slug: slug || undefined,
      },
      session.accessToken,
    );
    setLoading(false);
    if (result.ok) setSuccess("Perfil atualizado com sucesso.");
    else setError(result.detail ?? "Erro ao atualizar perfil.");
  }

  async function handleSalvarSenha(e: React.FormEvent) {
    e.preventDefault();
    if (!session?.accessToken) return;
    clearMessages();
    if (novaSenha !== confirmarSenha) {
      setError("Nova senha e confirmacao nao coincidem.");
      return;
    }
    if (novaSenha.length < 8) {
      setError("A nova senha deve ter pelo menos 8 caracteres.");
      return;
    }

    setLoading(true);
    const result = await patchConfiguracao(
      "senha",
      { senha_atual: senhaAtual, nova_senha: novaSenha },
      session.accessToken,
    );
    setLoading(false);

    if (result.ok) {
      setSuccess("Senha alterada com sucesso.");
      setSenhaAtual("");
      setNovaSenha("");
      setConfirmarSenha("");
    } else {
      setError(result.detail ?? "Erro ao alterar senha.");
    }
  }

  async function handleSalvarTema(e: React.FormEvent) {
    e.preventDefault();
    if (!session?.accessToken) return;
    clearMessages();

    setLoading(true);
    const result = await patchConfiguracao(
      "tema",
      { accent_color: accentColor, bg_color: bgColor, logo_url: logoUrl || null },
      session.accessToken,
    );
    setLoading(false);

    if (result.ok) {
      if (typeof window !== "undefined") {
        const raw = window.localStorage.getItem(AUTH_STORAGE_KEY);
        if (raw) {
          try {
            const s = JSON.parse(raw);
            s.accentColor = accentColor;
            s.bgColor = bgColor;
            s.logoUrl = logoUrl || null;
            window.localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(s));
          } catch {
            // noop
          }
        }
      }
      setSuccess("Tema salvo. As cores serao aplicadas no proximo login.");
    } else {
      setError(result.detail ?? "Erro ao salvar tema.");
    }
  }

  async function handleSalvarNotificacoes(e: React.FormEvent) {
    e.preventDefault();
    if (!session?.accessToken) return;
    clearMessages();

    setLoading(true);
    const result = await patchConfiguracao(
      "notificacoes",
      { notif_ativo: notifAtivo, notif_horas_antes: notifHoras },
      session.accessToken,
    );
    setLoading(false);
    if (result.ok) setSuccess("Preferencias salvas.");
    else setError(result.detail ?? "Erro ao salvar preferencias.");
  }

  return (
    <div className={styles.page}>
      <div className={styles.shell}>
        <aside className={styles.sidebar}>
          <button type="button" onClick={() => router.back()} className={styles.backButton}>
            <ArrowLeft size={14} />
            Voltar
          </button>
          <div className={styles.sidebarHeader}>
            <Settings size={15} />
            Configuracoes
          </div>
          <nav className={styles.navList}>
            {SECTIONS.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                type="button"
                className={`${styles.navItem} ${activeSection === id ? styles.navItemActive : ""}`}
                onClick={() => {
                  setActiveSection(id);
                  clearMessages();
                }}
              >
                <Icon size={14} />
                {label}
              </button>
            ))}
          </nav>
        </aside>

        <div className={styles.content}>
          {success && <div className={styles.alertSuccess}>{success}</div>}
          {error && <div className={styles.alertError}>{error}</div>}

          {activeSection === "perfil" && (
            <form onSubmit={handleSalvarPerfil} className={styles.card}>
              <div className={styles.cardHeader}>
                <p className={styles.eyebrow}>Conta</p>
                <h2 className={styles.cardTitle}>Perfil do estabelecimento</h2>
                <p className={styles.cardDesc}>Informacoes publicas exibidas no agendamento.</p>
              </div>

              <div className={styles.cardBody}>
                <div className={styles.fieldGroup}>
                  <div className={styles.field}>
                    <label className={styles.fieldLabel} htmlFor="nome">Nome do estabelecimento</label>
                    <input id="nome" className="input" value={nome} onChange={(e) => setNome(e.target.value)} />
                  </div>
                  <hr className={styles.divider} />
                  <div className={styles.field}>
                    <label className={styles.fieldLabel} htmlFor="endereco">Endereco</label>
                    <input id="endereco" className="input" value={endereco} onChange={(e) => setEndereco(e.target.value)} />
                  </div>
                  <div className={styles.field}>
                    <label className={styles.fieldLabel} htmlFor="whatsapp">WhatsApp</label>
                    <input id="whatsapp" className="input" value={whatsapp} onChange={(e) => setWhatsapp(e.target.value)} />
                  </div>
                  <hr className={styles.divider} />
                  <div className={styles.field}>
                    <label className={styles.fieldLabel} htmlFor="slug">Slug (URL publica)</label>
                    <input id="slug" className="input" value={slug} onChange={(e) => setSlug(e.target.value)} />
                    <span className={styles.fieldHint}>Seu link publico usa este identificador.</span>
                  </div>
                </div>
              </div>

              <div className={styles.cardFooter}>
                <button type="submit" className="btn btn-accent" disabled={loading}>
                  {loading ? "Salvando..." : "Salvar perfil"}
                </button>
              </div>
            </form>
          )}

          {activeSection === "senha" && (
            <form onSubmit={handleSalvarSenha} className={styles.card}>
              <div className={styles.cardHeader}>
                <p className={styles.eyebrow}>Seguranca</p>
                <h2 className={styles.cardTitle}>Trocar senha</h2>
                <p className={styles.cardDesc}>Use uma senha forte com pelo menos 8 caracteres.</p>
              </div>

              <div className={styles.cardBody}>
                <div className={styles.fieldGroup}>
                  <div className={styles.field}>
                    <label className={styles.fieldLabel}>Senha atual</label>
                    <input type="password" className="input" value={senhaAtual} onChange={(e) => setSenhaAtual(e.target.value)} />
                  </div>
                  <hr className={styles.divider} />
                  <div className={styles.fieldRow}>
                    <div className={styles.field}>
                      <label className={styles.fieldLabel}>Nova senha</label>
                      <input type="password" className="input" value={novaSenha} onChange={(e) => setNovaSenha(e.target.value)} />
                    </div>
                    <div className={styles.field}>
                      <label className={styles.fieldLabel}>Confirmar nova senha</label>
                      <input type="password" className="input" value={confirmarSenha} onChange={(e) => setConfirmarSenha(e.target.value)} />
                    </div>
                  </div>
                </div>
              </div>

              <div className={styles.cardFooter}>
                <button type="submit" className="btn btn-accent" disabled={loading}>
                  {loading ? "Salvando..." : "Alterar senha"}
                </button>
              </div>
            </form>
          )}

          {activeSection === "tema" && (
            <form onSubmit={handleSalvarTema} className={styles.card}>
              <div className={styles.cardHeader}>
                <p className={styles.eyebrow}>Aparencia</p>
                <h2 className={styles.cardTitle}>Tema e cores</h2>
                <p className={styles.cardDesc}>Personalize cores do painel e da pagina publica.</p>
              </div>

              <div className={styles.cardBody}>
                <div className={styles.fieldGroup}>
                  <div className={styles.field}>
                    <span className={styles.fieldLabel}>Paletas prontas</span>
                    <div className={styles.presetGrid}>
                      {PRESETS.map((preset) => (
                        <button
                          key={preset.label}
                          type="button"
                          className={`${styles.presetChip} ${activePreset === preset.label ? styles.presetChipActive : ""}`}
                          onClick={() => applyPreset(preset)}
                        >
                          <span className={styles.presetDot} style={{ background: preset.accent }} />
                          {preset.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  <hr className={styles.divider} />

                  <div className={styles.colorPickerRow}>
                    <div className={styles.colorPickerField}>
                      <span className={styles.fieldLabel}>Cor de destaque</span>
                      <div className={styles.colorPickerTrigger}>
                        <span className={styles.colorSwatch} style={{ background: accentColor }} />
                        <span className={styles.colorHex}>{accentColor}</span>
                        <input
                          type="color"
                          className={styles.colorPickerInput}
                          value={accentColor}
                          onChange={(e) => {
                            setAccentColor(e.target.value);
                            setActivePreset(null);
                            document.documentElement.style.setProperty("--accent", e.target.value);
                          }}
                        />
                      </div>
                    </div>

                    <div className={styles.colorPickerField}>
                      <span className={styles.fieldLabel}>Cor de fundo</span>
                      <div className={styles.colorPickerTrigger}>
                        <span className={styles.colorSwatch} style={{ background: bgColor }} />
                        <span className={styles.colorHex}>{bgColor}</span>
                        <input
                          type="color"
                          className={styles.colorPickerInput}
                          value={bgColor}
                          onChange={(e) => {
                            setBgColor(e.target.value);
                            setActivePreset(null);
                          }}
                        />
                      </div>
                    </div>
                  </div>

                  <div className={styles.field}>
                    <label className={styles.fieldLabel} htmlFor="logo-url">URL do logotipo</label>
                    <input id="logo-url" className="input" value={logoUrl ?? ""} onChange={(e) => setLogoUrl(e.target.value)} />
                    {logoUrl && <img src={logoUrl} alt="Preview do logo" className={styles.logoPreview} />}
                  </div>
                </div>
              </div>

              <div className={styles.cardFooter}>
                <button type="submit" className="btn btn-accent" disabled={loading}>
                  {loading ? "Salvando..." : "Salvar tema"}
                </button>
              </div>
            </form>
          )}

          {activeSection === "notificacoes" && (
            <form onSubmit={handleSalvarNotificacoes} className={styles.card}>
              <div className={styles.cardHeader}>
                <p className={styles.eyebrow}>Automacoes</p>
                <h2 className={styles.cardTitle}>Notificacoes</h2>
                <p className={styles.cardDesc}>Configure lembretes automaticos enviados aos clientes.</p>
              </div>

              <div className={styles.cardBody}>
                <div className={styles.fieldGroup}>
                  <label className={styles.checkboxRow}>
                    <input type="checkbox" checked={notifAtivo} onChange={(e) => setNotifAtivo(e.target.checked)} />
                    <div>
                      <div className={styles.checkboxLabel}>Enviar lembretes de agendamento</div>
                      <div className={styles.checkboxHint}>Mensagens automaticas por WhatsApp antes do horario.</div>
                    </div>
                  </label>

                  <hr className={styles.divider} />

                  <div className={styles.field}>
                    <label className={styles.fieldLabel}>Antecedencia do lembrete</label>
                    <select className="input" value={notifHoras} onChange={(e) => setNotifHoras(Number(e.target.value))} disabled={!notifAtivo}>
                      <option value={1}>1 hora antes</option>
                      <option value={2}>2 horas antes</option>
                      <option value={4}>4 horas antes</option>
                      <option value={8}>8 horas antes</option>
                      <option value={24}>24 horas antes</option>
                    </select>
                  </div>
                </div>
              </div>

              <div className={styles.cardFooter}>
                <button type="submit" className="btn btn-accent" disabled={loading}>
                  {loading ? "Salvando..." : "Salvar preferencias"}
                </button>
              </div>
            </form>
          )}

        </div>
      </div>
    </div>
  );
}
