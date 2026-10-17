import assert from "node:assert/strict";
import { test } from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import App from "../src/App";
import { createNavigation, readRoute, routeHash } from "../src/navigation";
import type { NavigationHost, Route } from "../src/navigation";

function openAddress(hash: string) {
  const location = new URL(`http://localhost:8321/${hash}`);
  Object.defineProperty(globalThis, "location", {
    configurable: true,
    value: location,
  });
  Object.defineProperty(globalThis, "window", {
    configurable: true,
    value: { location },
  });
}

class BrowserHistory implements NavigationHost {
  entries: { url: URL; state: unknown }[];
  cursor = 0;
  listeners = new Map<string, Set<() => void>>();
  history: NavigationHost["history"];
  constructor(hash = "") {
    this.entries = [
      {
        url: new URL(`http://localhost:8321/?workspace=local${hash}`),
        state: null,
      },
    ];
    const browser = this;
    this.history = {
      get state() {
        return browser.entries[browser.cursor].state;
      },
      pushState(state, _, address) {
        browser.entries.splice(browser.cursor + 1);
        browser.entries.push({
          url: new URL(address, browser.location),
          state,
        });
        browser.cursor++;
      },
      replaceState(state, _, address) {
        browser.entries[browser.cursor] = {
          url: new URL(address, browser.location),
          state,
        };
      },
      go(delta) {
        const cursor = browser.cursor + delta;
        if (cursor < 0 || cursor >= browser.entries.length) return;
        browser.cursor = cursor;
        browser.emit("popstate");
        browser.emit("hashchange");
      },
    };
  }
  get location() {
    return this.entries[this.cursor].url;
  }
  addEventListener(type: string, listener: () => void) {
    if (!this.listeners.has(type)) this.listeners.set(type, new Set());
    this.listeners.get(type)!.add(listener);
  }
  removeEventListener(type: string, listener: () => void) {
    this.listeners.get(type)?.delete(listener);
  }
  emit(type: string) {
    this.listeners.get(type)?.forEach((listener) => listener());
  }
  editHash(hash: string) {
    this.history.pushState(null, "", hash);
    this.emit("hashchange");
  }
}

const id = "1234567890abcdef1234567890abcdef";

test("new production and every editor tab survive serializing the address", () => {
  assert.equal(readRoute("#/novo").page, "new");
  for (const tab of [
    "brief",
    "script",
    "scenes",
    "audio",
    "cover",
    "publication",
    "versions",
  ] as const) {
    const route: Route = { page: "projects", projectId: id, tab };
    assert.deepEqual(readRoute(routeHash(route)), route);
  }
});

test("a horizontal project's timeline has its own persistent address", () => {
  const route: Route = { page: "projects", projectId: null, editId: id };
  assert.equal(routeHash(route), `#/edicao/${id}`);
  assert.deepEqual(readRoute(routeHash(route)), route);
  assert.deepEqual(readRoute(`#/edicao/${id}/extra`), { page: "projects", projectId: null });
});

test("legacy project links remain valid and unknown addresses recover to the library", () => {
  assert.deepEqual(readRoute(`#${id}`), { page: "projects", projectId: id });
  // The former combined "Voz e capa" tab now opens Áudio.
  assert.deepEqual(readRoute(`#/producoes/${id}/media`), {
    page: "projects",
    projectId: id,
    tab: "audio",
  });
  for (const hash of [
    "",
    "#%invalid",
    "#/does-not-exist",
    "#/producoes/invalid-id",
  ]) {
    assert.deepEqual(readRoute(hash), { page: "projects", projectId: null });
  }
});

test("navigation, reload, Back and Forward retain the selected page", () => {
  const browser = new BrowserHistory();
  let route = readRoute(browser.location.hash);
  let navigation = createNavigation(
    browser,
    () => true,
    (next) => {
      route = next;
    },
  );
  navigation.navigate({ page: "environment", projectId: null });
  assert.equal(browser.location.hash, "#/configuracoes/agentes");
  assert.equal(browser.location.search, "?workspace=local");
  navigation.dispose();
  route = readRoute(browser.location.hash); // Fresh app initialization after reload.
  assert.equal(route.page, "environment");
  navigation = createNavigation(
    browser,
    () => true,
    (next) => {
      route = next;
    },
  );
  navigation.navigate({ page: "queue", projectId: null });
  browser.history.go(-1);
  assert.equal(route.page, "environment");
  browser.history.go(1);
  assert.equal(route.page, "queue");
  const length = browser.entries.length;
  navigation.navigate(route);
  assert.equal(browser.entries.length, length);
  navigation.dispose();
  assert.equal(
    [...browser.listeners.values()].reduce(
      (sum, listeners) => sum + listeners.size,
      0,
    ),
    0,
  );
});

test("cancelled Back preserves the editor URL, draft owner and forward history", () => {
  const browser = new BrowserHistory("#/fila");
  let dirty = false;
  let prompts = 0;
  let route = readRoute(browser.location.hash);
  const navigation = createNavigation(
    browser,
    (from, to) => {
      if (from.projectId === to.projectId || !dirty) return true;
      prompts++;
      return false;
    },
    (next) => {
      route = next;
    },
  );
  navigation.navigate({ page: "projects", projectId: id, tab: "script" });
  dirty = true;
  navigation.navigate({ page: "projects", projectId: id, tab: "scenes" });
  browser.history.go(-1); // Tabs keep the same draft.
  assert.equal(route.tab, "script");
  assert.equal(prompts, 0);
  browser.history.go(-1); // Leaving the project is rejected.
  assert.equal(route.projectId, id);
  assert.equal(browser.location.hash, `#/producoes/${id}/script`);
  assert.equal(prompts, 1);
  browser.history.go(1);
  assert.equal(route.tab, "scenes");
  dirty = false;
  browser.history.go(-2);
  assert.equal(route.page, "queue");
  navigation.dispose();
});

test("manually editing the hash synchronizes the route and respects the leave guard", () => {
  const browser = new BrowserHistory();
  let allow = true;
  let route = readRoute(browser.location.hash);
  const navigation = createNavigation(
    browser,
    () => allow,
    (next) => {
      route = next;
    },
  );
  browser.editHash("#/novo");
  assert.equal(route.page, "new");
  allow = false;
  browser.editHash("#/conexoes");
  assert.equal(route.page, "new");
  assert.equal(browser.location.hash, "#/novo");
  navigation.dispose();
});

// Fresh mounts reproduce the state initialization used after a browser refresh.
// Browser interactions and layout are covered separately by Playwright.
for (const [hash, label] of [
  ["#/conexoes", "Configurações"],
  ["#/fila", "Fila de produção"],
  ["#/producoes", "Produções"],
]) {
  test(`refresh restores ${label} from the address`, () => {
    openAddress(hash);
    const html = renderToStaticMarkup(createElement(App));
    const active = html
      .match(/<button class="nav-item active"[^>]*>(.*?)<\/button>/s)?.[1]
      .replace(/<[^>]*>/g, "");
    assert.equal(active, label);
  });
}

test("settings sections have distinct persistent addresses and preserve legacy links", () => {
  for (const settings of ["agents", "voices", "environment"] as const) {
    const route: Route = { page: "environment", projectId: null, settings };
    assert.deepEqual(readRoute(routeHash(route)), route);
  }
  assert.equal(routeHash(readRoute("#/conexoes")), "#/configuracoes/agentes");
  assert.equal(
    routeHash(readRoute("#/configuracoes")),
    "#/configuracoes/agentes",
  );
  assert.equal(readRoute("#/configuracoes/inexistente").page, "projects");
  const browser = new BrowserHistory("#/configuracoes/agentes");
  let route = readRoute(browser.location.hash);
  const navigation = createNavigation(
    browser,
    () => true,
    (next) => {
      route = next;
    },
  );
  navigation.navigate({
    page: "environment",
    projectId: null,
    settings: "voices",
  });
  navigation.navigate({
    page: "environment",
    projectId: null,
    settings: "environment",
  });
  browser.history.go(-1);
  assert.equal(route.settings, "voices");
  assert.equal(browser.location.hash, "#/configuracoes/vozes");
  browser.history.go(1);
  assert.equal(route.settings, "environment");
  navigation.dispose();
});
