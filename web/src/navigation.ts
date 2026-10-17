import { useCallback, useEffect, useRef, useState } from "react";

export type Page = "projects" | "queue" | "environment" | "new";
export type Tab =
  | "brief"
  | "script"
  | "scenes"
  | "audio"
  | "cover"
  | "ending"
  | "publication"
  | "art"
  | "materials"
  | "versions"
  | "costs";
export type SettingsSection =
  | "agents"
  | "channels"
  | "voices"
  | "environment"
  | "costs";
export type Route = {
  page: Page;
  projectId: string | null;
  tab?: Tab;
  settings?: SettingsSection;
};

const settingsPaths: Record<SettingsSection, string> = {
  agents: "agentes",
  channels: "canais",
  voices: "vozes",
  environment: "ambiente",
  costs: "custos",
};

const pages: Record<Page, string> = {
  projects: "producoes",
  queue: "fila",
  environment: "configuracoes",
  new: "novo",
};
const tabs = new Set<Tab>([
  "brief",
  "script",
  "scenes",
  "audio",
  "cover",
  "ending",
  "publication",
  "art",
  "materials",
  "versions",
  "costs",
]);
const projectId = /^[a-f0-9]{32}$/;
const home: Route = { page: "projects", projectId: null };

export function readRoute(hash: string): Route {
  const path = hash.replace(/^#\/?/, "");
  // Preserve links created before navigation used named routes.
  if (projectId.test(path)) return { ...home, projectId: path };
  const [section, id, tab, extra] = path.split("/");
  if (
    (section === "configuracoes" || section === "conexoes") &&
    !tab &&
    !extra
  ) {
    const settings = (Object.keys(settingsPaths) as SettingsSection[]).find(
      (key) => settingsPaths[key] === id,
    );
    if (!id || settings)
      return {
        page: "environment",
        projectId: null,
        settings: settings ?? "agents",
      };
  }
  if (section === "producoes" && id && projectId.test(id) && !extra) {
    // "media" was the combined voice and cover tab; its links now open Áudio.
    const known = tab === "media" ? "audio" : tab;
    return {
      ...home,
      projectId: id,
      ...(tabs.has(known as Tab) ? { tab: known as Tab } : {}),
    };
  }
  if (!id) {
    const page = (Object.keys(pages) as Page[]).find(
      (key) => pages[key] === section,
    );
    if (page) return { page, projectId: null };
  }
  return { ...home };
}

export function routeHash(route: Route): string {
  return route.projectId
    ? `#/producoes/${route.projectId}${route.tab ? `/${route.tab}` : ""}`
    : route.page === "environment"
      ? `#/configuracoes/${settingsPaths[route.settings ?? "agents"]}`
      : `#/${pages[route.page]}`;
}

export interface NavigationHost {
  location: { hash: string; pathname: string; search: string };
  history: {
    state: unknown;
    pushState(data: unknown, unused: string, url: string): void;
    replaceState(data: unknown, unused: string, url: string): void;
    go(delta: number): void;
  };
  addEventListener(type: string, listener: () => void): void;
  removeEventListener(type: string, listener: () => void): void;
}

function historyIndex(state: unknown): number | null {
  if (
    state &&
    typeof state === "object" &&
    "mycutIndex" in state &&
    typeof state.mycutIndex === "number" &&
    Number.isSafeInteger(state.mycutIndex)
  )
    return state.mycutIndex;
  return null;
}

export function createNavigation(
  host: NavigationHost,
  canLeave: (from: Route, to: Route) => boolean,
  onChange: (route: Route) => void,
) {
  let current = readRoute(host.location.hash);
  let index = historyIndex(host.history.state) ?? 0;
  let restoring = false;
  const address = (route: Route) =>
    host.location.pathname + host.location.search + routeHash(route);
  const replace = () =>
    host.history.replaceState({ mycutIndex: index }, "", address(current));
  replace();

  const changed = () => {
    const nextIndex = historyIndex(host.history.state);
    if (restoring) {
      // Cancelling Back/Forward returns to the original history entry and keeps the draft mounted.
      if (nextIndex === index) restoring = false;
      return;
    }
    const next = readRoute(host.location.hash);
    if (routeHash(next) === routeHash(current)) {
      if (nextIndex !== null) index = nextIndex;
      replace();
      return;
    }
    if (!canLeave(current, next)) {
      if (nextIndex !== null && nextIndex !== index) {
        restoring = true;
        host.history.go(index - nextIndex);
      } else {
        // A manually edited hash has no app history index to traverse back to.
        replace();
      }
      return;
    }
    index = nextIndex ?? index + 1;
    current = next;
    replace();
    onChange(current);
  };
  host.addEventListener("popstate", changed);
  host.addEventListener("hashchange", changed);
  return {
    navigate(next: Route) {
      if (
        restoring ||
        routeHash(next) === routeHash(current) ||
        !canLeave(current, next)
      )
        return;
      current = next;
      host.history.pushState({ mycutIndex: ++index }, "", address(next));
      onChange(current);
    },
    dispose() {
      host.removeEventListener("popstate", changed);
      host.removeEventListener("hashchange", changed);
    },
  };
}

export function useNavigation(canLeave: (from: Route, to: Route) => boolean) {
  const [route, setRoute] = useState(() => readRoute(window.location.hash));
  const navigation = useRef<ReturnType<typeof createNavigation> | null>(null);
  useEffect(() => {
    const controller = createNavigation(window, canLeave, setRoute);
    navigation.current = controller;
    setRoute(readRoute(window.location.hash));
    return () => {
      controller.dispose();
      navigation.current = null;
    };
  }, [canLeave]);
  const navigate = useCallback(
    (next: Route) => navigation.current?.navigate(next),
    [],
  );
  return { route, navigate };
}
