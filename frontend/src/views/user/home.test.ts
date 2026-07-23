import { flushPromises, mount } from "@vue/test-utils";
import { createPinia } from "pinia";
import { describe, expect, it } from "vitest";
import { createMemoryHistory, createRouter } from "vue-router";

import HomeView from "./home.vue";

async function mountHome() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/", name: "home", component: HomeView },
      {
        path: "/workflow/new",
        name: "workflow-new",
        component: { template: "<div />" },
      },
      { path: "/:pathMatch(.*)*", component: { template: "<div />" } },
    ],
  });
  await router.push("/");
  await router.isReady();
  const wrapper = mount(HomeView, {
    global: { plugins: [createPinia(), router] },
  });
  return { wrapper, router };
}

describe("User home", () => {
  it("offers the three approved output choices with one filled primary action", async () => {
    const { wrapper } = await mountHome();

    expect(wrapper.findAll("[data-testid='workflow-choice']")).toHaveLength(3);
    expect(wrapper.findAll(".oa-button--primary")).toHaveLength(1);
    expect(wrapper.text()).toContain("制作销售汇报");
    expect(wrapper.text()).toContain("分析销售数据");
    expect(wrapper.text()).toContain("两项一起完成");
  });

  it("carries the selected output mode into the new workflow", async () => {
    const { wrapper, router } = await mountHome();

    await wrapper
      .findAll("[data-testid='workflow-choice']")[2]
      .trigger("click");
    await wrapper.get("[data-testid='continue-workflow']").trigger("click");
    await flushPromises();

    expect(router.currentRoute.value).toMatchObject({
      name: "workflow-new",
      query: { mode: "combined" },
    });
  });
});
