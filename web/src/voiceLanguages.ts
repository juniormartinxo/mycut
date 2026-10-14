import type { VoiceCatalog } from "./types";

type Voice = VoiceCatalog["voices"][number];
const preferenceKey = "mycut:voice-language:v1";
const names = new Intl.DisplayNames(["pt-BR"], { type: "language" });

export function languageName(code: string) {
  try {
    const name = names.of(code) || code;
    return name.charAt(0).toLocaleUpperCase("pt-BR") + name.slice(1);
  } catch {
    return code;
  }
}

export function matchesLanguage(voice: Voice, language: string) {
  if (language === "all") return true;
  if (language === "unknown") return !voice.language;
  return voice.language === language;
}

export function savedVoiceLanguage() {
  try {
    const value = window.localStorage.getItem(preferenceKey);
    if (value && /^(all|unknown|[a-z]{2,3})$/.test(value)) return value;
  } catch {
    /* The filter still works if browser storage is unavailable. */
  }
  return "pt";
}

export function saveVoiceLanguage(value: string) {
  try {
    window.localStorage.setItem(preferenceKey, value);
  } catch {
    /* Optional preference. */
  }
}

const accents: Record<string, string> = {
  brazilian: "Brasileiro",
  "pt-brazilian": "Brasileiro",
  portuguese: "Portugal",
  "pt-portuguese": "Portugal",
  "pt-european": "Portugal",
  american: "Americano",
  british: "Britânico",
  australian: "Australiano",
};

export function voiceDescription(voice: Voice) {
  const details = [
    voice.name,
    voice.language ? languageName(voice.language) : "Idioma não informado",
  ];
  if (voice.accent)
    details.push(accents[voice.accent.toLowerCase()] || voice.accent);
  if (voice.category === "cloned") details.push("clonada");
  return details.join(" · ");
}
