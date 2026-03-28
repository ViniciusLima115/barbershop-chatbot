# Spec: Upsell de upgrade ao adicionar profissional no plano básico

**Data:** 2026-03-28

## Problema

No plano básico (limite de 1 profissional), ao clicar "Adicionar profissional" quando o limite já foi atingido, o modal de cadastro abre normalmente. O aviso passivo abaixo do botão não impede a ação nem orienta o usuário para o upgrade.

## Solução

Interceptar o clique e exibir um modal de upsell que comunica o limite e direciona para uma nova página `/upgrade`.

---

## Componentes

### 1. Interceptação do clique em `gestao/page.tsx`

- Nova state: `showUpgradeModal: boolean`
- Condição de intercepção: `!isPremiumPlan && limiteBarbeirosAtingido`
- Quando verdadeira: o clique em "Adicionar profissional" abre `showUpgradeModal = true` em vez de `abrirModalBarbeiro()`
- O botão "Criar primeiro profissional" do empty state não muda — quando não há profissionais o limite não foi atingido

### 2. Modal de upsell (inline em `gestao/page.tsx`)

Usa o componente `<Modal>` existente em `components/Modal.tsx`.

- **Título:** "Limite do plano básico atingido"
- **Corpo:** "O plano básico permite 1 profissional ativo. Com o Premium você pode cadastrar até 3 profissionais e ter acesso a dashboard financeiro, análise de clientes e suporte prioritário."
- **Ação primária:** botão "Fazer upgrade" → navega para `/upgrade`
- **Ação secundária:** botão "Agora não" → fecha o modal (`showUpgradeModal = false`)
- Sem lógica de pagamento

### 3. Página `/upgrade` (`frontend/app/upgrade/page.tsx`)

Nova rota Next.js com `page.module.css` próprio. Usa os tokens CSS e padrões visuais do design system existente.

**Layout:**
- Botão "← Voltar para gestão" no topo (link para `/gestao`)
- Heading "Escolha seu plano"
- Dois cards lado a lado (coluna única em mobile): Básico e Premium
- Card Premium com destaque visual (borda accent, badge "Recomendado")

**Comparativo de features:**

| Feature | Básico | Premium |
|---|---|---|
| Profissionais ativos | 1 | até 3 |
| Agendamentos | Ilimitados | Ilimitados |
| Dashboard financeiro | — | ✓ |
| Análise de clientes | — | ✓ |
| Ranking de serviços | — | ✓ |
| Suporte | — | Prioritário |

**CTA:**
- Plano Básico: botão desabilitado "Plano atual"
- Plano Premium: botão desabilitado com texto "Em breve" (placeholder para integração futura de pagamento)
- Preço mockado: "R$ 49/mês"

---

## Arquivos afetados

| Arquivo | Alteração |
|---|---|
| `frontend/app/gestao/page.tsx` | Adiciona `showUpgradeModal` state + interceptação do clique + modal de upsell |
| `frontend/app/upgrade/page.tsx` | Novo — página de comparativo de planos |
| `frontend/app/upgrade/page.module.css` | Novo — estilos da página de upgrade |

---

## Fora de escopo

- Integração com gateway de pagamento
- Lógica de ativação do plano premium
- Alteração do fluxo de downgrade
