import { createPinia } from "pinia";
import { createApp } from "vue";
import type { RouterHistory } from "vue-router";

import App from "./App.vue";
import { createOfficeAiRouter } from "./router";

interface CreateOfficeAiAppOptions {
  history?: RouterHistory;
}
export function createOfficeAiApp(options: CreateOfficeAiAppOptions = {}) {
  const app = createApp(App);
  const pinia = createPinia();
  const router = createOfficeAiRouter({ history: options.history, pinia });
  app.use(pinia);
  app.use(router);
  return { app, pinia, router };
}
