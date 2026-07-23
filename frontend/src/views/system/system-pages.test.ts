import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import NoPermissionView from "./no-permission.vue";
import NotFoundView from "./not-found.vue";

describe("System pages", () => {
  it("explains denied access without exposing protected context", () => {
    const wrapper = mount(NoPermissionView, {
      global: {
        stubs: { RouterLink: { template: "<a><slot /></a>" } },
      },
    });

    expect(wrapper.text()).toContain("没有访问权限");
    expect(wrapper.text()).toContain("返回工作台");
  });

  it("offers a useful recovery path for unknown routes", () => {
    const wrapper = mount(NotFoundView, {
      global: {
        stubs: { RouterLink: { template: "<a><slot /></a>" } },
      },
    });

    expect(wrapper.text()).toContain("页面不存在");
    expect(wrapper.text()).toContain("返回首页");
  });
});
