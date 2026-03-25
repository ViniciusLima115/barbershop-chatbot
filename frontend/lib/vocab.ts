export type TipoServico = "barbearia" | "salao_beleza" | "estetica_automotiva" | string;

export type VocabEntry = {
  profissional: string;
  estabelecimento: string;
  profissionalPlural: string;
};

const vocabMap: Record<string, VocabEntry> = {
  barbearia: {
    profissional: "Barbeiro",
    estabelecimento: "Barbearia",
    profissionalPlural: "Barbeiros",
  },
  salao_beleza: {
    profissional: "Atendente",
    estabelecimento: "Salão",
    profissionalPlural: "Atendentes",
  },
  estetica_automotiva: {
    profissional: "Detailer",
    estabelecimento: "Estética",
    profissionalPlural: "Detailers",
  },
};

const defaultVocab: VocabEntry = vocabMap["barbearia"];

export function getVocab(tipo: TipoServico | null | undefined): VocabEntry {
  if (!tipo) return defaultVocab;
  return vocabMap[tipo] ?? defaultVocab;
}
