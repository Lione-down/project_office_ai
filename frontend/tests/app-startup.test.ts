import { describe, expect, it } from "vitest";
import { createMemoryHistory } from "vue-router";

import { createOfficeAiApp } from "../src/bootstrap";

describe("application startup", () => {
  it("mounts the Vue application with Router and Pinia", async () => {
    const root = document.createElement("div");
    const { app, router } = createOfficeAiApp({ history: createMemoryHistory() });

    await router.push({ name: "login" });
    await router.isReady();
    app.mount(root);

    expect(root.querySelector("[data-testid='app-root']")).not.toBeNull();
  });
});
