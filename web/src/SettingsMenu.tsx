import { Bot, Coins, Headphones, Monitor, Tv } from "lucide-react";
import type { SettingsSection } from "./navigation";
import "./Settings.css";

export const settingsSections = [
  {
    id: "agents",
    label: "Agentes",
    description: "Escolha quem pesquisa, escreve e cria seus Shorts.",
    icon: Bot,
  },
  {
    id: "channels",
    label: "Canais",
    description: "Nome, marca e voz que cada produção herda do seu canal.",
    icon: Tv,
  },
  {
    id: "voices",
    label: "Vozes",
    description: "Encontre a voz do seu canal e ajuste a narração.",
    icon: Headphones,
  },
  {
    id: "environment",
    label: "Ambiente",
    description: "Configure os CLIs, o navegador e os serviços de produção.",
    icon: Monitor,
  },
  {
    id: "costs",
    label: "Custos",
    description: "Preços usados para estimar o consumo de cada projeto.",
    icon: Coins,
  },
] as const;

export function SettingsMenu({
  section,
  onNavigate,
  placement,
}: {
  section: SettingsSection;
  onNavigate: (section: SettingsSection) => void;
  placement: "sidebar" | "page";
}) {
  return (
    <nav
      id={`settings-${placement}-menu`}
      className={`settings-submenu settings-submenu-${placement}`}
      aria-label="Seções de configurações"
    >
      {settingsSections.map(({ id, label, icon: Icon }) => (
        <button
          key={id}
          type="button"
          aria-current={section === id ? "page" : undefined}
          onClick={() => onNavigate(id)}
        >
          <Icon size={16} aria-hidden="true" />
          {label}
        </button>
      ))}
    </nav>
  );
}
