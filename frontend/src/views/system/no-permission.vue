<template>
  <main class="system-page" lang="zh-CN">
    <p>403</p>
    <h1>没有访问权限</h1>
    <span>当前账号不能进入这个区域。如需管理权限，请联系管理员。</span>
    <RouterLink class="oa-button oa-button--primary" to="/">返回工作台</RouterLink>
  </main>
</template>

<style scoped>
.system-page {
  display: grid;
  width: min(100% - 40px, 620px);
  min-height: 70vh;
  margin: 0 auto;
  place-content: center;
  justify-items: start;
}

p {
  margin: 0;
  color: var(--oa-accent);
  font-size: 14px;
  font-weight: 800;
}

h1 {
  margin: 10px 0 12px;
  font-size: clamp(38px, 7vw, 64px);
  line-height: 1.05;
}

span {
  max-width: 520px;
  color: var(--oa-muted);
  line-height: 1.7;
}

a {
  display: inline-grid;
  margin-top: 28px;
  place-items: center;
  text-decoration: none;
}
</style>
