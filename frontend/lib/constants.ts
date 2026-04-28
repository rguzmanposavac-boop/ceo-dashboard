export const SIGNAL_COLORS: Record<string, string> = {
  COMPRA_FUERTE: "#3de88a",
  COMPRA:        "#f5c542",
  VIGILAR:       "#ff8c42",
  EVITAR:        "#ff5e5e",
};

export const REGIME_COLORS: Record<string, string> = {
  CRISIS:  "#ff5e5e",
  BAJISTA: "#ff8c42",
  NORMAL:  "#7090b0",
  ALCISTA: "#3de88a",
  REBOTE:  "#5ba4ff",
};

export const HORIZON_LABELS: Record<string, string> = {
  CORTO_PLAZO:   "Corto plazo",
  MEDIANO_PLAZO: "Mediano plazo",
  LARGO_PLAZO:   "Largo plazo",
};

// Top-3 CEO profiles per regime (from PROFILE_REGIME_SCORE in CLAUDE.md)
export const FAVORED_CEO_PROFILES: Record<string, string[]> = {
  CRISIS:  ["Racional Paciente", "Disciplinado Sistémico", "Paranoico Estratégico"],
  BAJISTA: ["Racional Paciente", "Disciplinado Sistémico", "Paranoico Estratégico"],
  NORMAL:  ["Visionario Analítico", "Disciplinado Sistémico", "Paranoico Estratégico"],
  ALCISTA: ["Visionario Sistémico", "Visionario Analítico", "Narcisista Visionario"],
  REBOTE:  ["Narcisista Visionario", "Visionario Sistémico", "Paranoico Estratégico"],
};
