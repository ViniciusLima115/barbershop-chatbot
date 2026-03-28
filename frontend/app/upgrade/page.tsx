"use client";

import Link from "next/link";
import { ArrowLeft, Check, Minus } from "lucide-react";
import { useAuthSession } from "@/services/auth";
import styles from "./page.module.css";

type PlanKey = "gratis" | "basico" | "premium";

type Feature = {
  label: string;
  gratis: boolean | string;
  basico: boolean | string;
  premium: boolean | string;
};

const FEATURES: Feature[] = [
  {
    label: "Profissionais ativos",
    gratis: "1",
    basico: "2",
    premium: "3+",
  },
  {
    label: "Agendamentos por mês",
    gratis: "30",
    basico: "Ilimitados",
    premium: "Ilimitados",
  },
  {
    label: "Dashboard básico",
    gratis: false,
    basico: true,
    premium: true,
  },
  {
    label: "Dashboard financeiro completo",
    gratis: false,
    basico: false,
    premium: true,
  },
  {
    label: "Análise de clientes",
    gratis: false,
    basico: false,
    premium: true,
  },
  {
    label: "Ranking de serviços",
    gratis: false,
    basico: false,
    premium: true,
  },
  {
    label: "Notificações WhatsApp",
    gratis: false,
    basico: true,
    premium: true,
  },
  {
    label: "Chatbot automático",
    gratis: false,
    basico: true,
    premium: true,
  },
  {
    label: "Suporte prioritário",
    gratis: false,
    basico: false,
    premium: true,
  },
];

function FeatureValue({ value }: { value: boolean | string }) {
  if (typeof value === "string") {
    return <span className={styles.featureText}>{value}</span>;
  }
  if (value) {
    return <Check size={16} className={`${styles.featureIcon} ${styles.featureIconCheck}`} />;
  }
  return <Minus size={16} className={`${styles.featureIcon} ${styles.featureIconMissing}`} />;
}

export default function UpgradePage() {
  const session = useAuthSession();
  const currentPlan = (session?.plan ?? "gratis") as PlanKey;

  function planButton(plan: PlanKey, price: string, label: string) {
    const isCurrent = currentPlan === plan;
    return isCurrent ? (
      <button disabled className={`${styles.ctaButton} ${styles.ctaButtonSecondary}`}>
        Plano atual
      </button>
    ) : (
      <button disabled className={`${styles.ctaButton} ${styles.ctaButtonPrimary}`}>
        {label} — Em breve
      </button>
    );
  }

  return (
    <div className={styles.page}>
      <div className={styles.shell}>
        <Link href="/gestao" className={styles.backLink}>
          <ArrowLeft size={14} />
          Voltar para gestão
        </Link>

        <div className={styles.header}>
          <p className={styles.eyebrow}>Planos</p>
          <h1 className={styles.title}>Escolha seu plano</h1>
          <p className={styles.subtitle}>
            Comece grátis e faça upgrade quando precisar de mais recursos.
          </p>
        </div>

        <div className={styles.plansGrid}>
          {/* Plano Grátis */}
          <div className={styles.planCard}>
            <div className={styles.planCardHeader}>
              <div className={styles.planBadgeRow}>
                <h2 className={styles.planName}>Grátis</h2>
              </div>
              <p className={styles.planPrice}>R$ 0</p>
              <p className={styles.planDescription}>
                Para experimentar a plataforma com o essencial.
              </p>
            </div>

            <ul className={styles.featureList}>
              {FEATURES.map((f) => (
                <li key={f.label} className={styles.featureItem}>
                  <FeatureValue value={f.gratis} />
                  {f.label}
                </li>
              ))}
            </ul>

            {planButton("gratis", "R$0", "Usar Grátis")}
          </div>

          {/* Plano Básico */}
          <div className={`${styles.planCard} ${currentPlan === "basico" ? styles.planCardHighlight : ""}`}>
            <div className={styles.planCardHeader}>
              <div className={styles.planBadgeRow}>
                <h2 className={styles.planName}>Básico</h2>
                {currentPlan !== "basico" && <span className={styles.planBadge}>Popular</span>}
              </div>
              <p className={styles.planPrice}>
                R$ 29<span className={styles.planPriceSub}>/mês</span>
              </p>
              <p className={styles.planDescription}>
                Para quem quer crescer com WhatsApp, chatbot e mais profissionais.
              </p>
            </div>

            <ul className={styles.featureList}>
              {FEATURES.map((f) => (
                <li key={f.label} className={styles.featureItem}>
                  <FeatureValue value={f.basico} />
                  {f.label}
                </li>
              ))}
            </ul>

            {planButton("basico", "R$29", "Assinar Básico")}
          </div>

          {/* Plano Premium */}
          <div className={`${styles.planCard} ${currentPlan === "premium" ? styles.planCardHighlight : styles.planCardPremium}`}>
            <div className={styles.planCardHeader}>
              <div className={styles.planBadgeRow}>
                <h2 className={styles.planName}>Premium</h2>
                <span className={styles.planBadge}>Recomendado</span>
              </div>
              <p className={styles.planPrice}>
                R$ 49<span className={styles.planPriceSub}>/mês</span>
              </p>
              <p className={styles.planDescription}>
                Para estabelecimentos que querem crescer com dados e análises completas.
              </p>
            </div>

            <ul className={styles.featureList}>
              {FEATURES.map((f) => (
                <li key={f.label} className={styles.featureItem}>
                  <FeatureValue value={f.premium} />
                  {f.label}
                </li>
              ))}
            </ul>

            {planButton("premium", "R$49", "Assinar Premium")}
          </div>
        </div>

        <p className={styles.footerNote}>
          Pagamento online em breve. Por enquanto, entre em contato com o suporte para fazer upgrade.
        </p>
      </div>
    </div>
  );
}
