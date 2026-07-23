<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";

type WorkflowMode = "pptx" | "xlsx" | "combined";

const router = useRouter();
const selectedMode = ref<WorkflowMode>("combined");
const choices: Array<{
  mode: WorkflowMode;
  title: string;
  description: string;
  fileLabel: string;
}> = [
  {
    mode: "pptx",
    title: "制作销售汇报",
    description: "生成可下载的 PPTX",
    fileLabel: "PPTX",
  },
  {
    mode: "xlsx",
    title: "分析销售数据",
    description: "生成分析表与经营看板",
    fileLabel: "XLSX",
  },
  {
    mode: "combined",
    title: "两项一起完成",
    description: "使用同一份材料生成 PPTX 和 XLSX",
    fileLabel: "PPTX + XLSX",
  },
];

async function continueWorkflow() {
  await router.push({
    name: "workflow-new",
    query: { mode: selectedMode.value },
  });
}
</script>

<template>
  <section class="home-page" lang="zh-CN">
    <header>
      <p>Office AI 工作台</p>
      <h1>今天想完成什么？</h1>
      <span>选择一项工作，剩下的交给系统。</span>
    </header>

    <div class="choice-grid" role="radiogroup" aria-label="选择输出">
      <button
        v-for="choice in choices"
        :key="choice.mode"
        type="button"
        class="workflow-choice"
        :class="{ selected: selectedMode === choice.mode }"
        data-testid="workflow-choice"
        role="radio"
        :aria-checked="selectedMode === choice.mode"
        @click="selectedMode = choice.mode"
      >
        <span class="workflow-choice__kind">{{ choice.fileLabel }}</span>
        <strong>{{ choice.title }}</strong>
        <small>{{ choice.description }}</small>
        <span v-if="selectedMode === choice.mode" class="selected-mark">已选择</span>
      </button>
    </div>

    <button
      type="button"
      class="oa-button oa-button--primary continue-button"
      data-testid="continue-workflow"
      @click="continueWorkflow"
    >
      继续
    </button>

    <section class="recent-section" aria-labelledby="recent-title">
      <div>
        <h2 id="recent-title">最近任务</h2>
        <RouterLink to="/tasks">查看全部</RouterLink>
      </div>
      <p>完成生成后，任务进度、质量结果和下载入口会显示在这里。</p>
    </section>
  </section>
</template>

<style scoped>
.home-page {
  padding: clamp(52px, 8vw, 96px) clamp(20px, 5vw, 64px) 56px;
}

header {
  margin: 0 auto 40px;
  text-align: center;
}

header p {
  margin: 0 0 10px;
  color: var(--oa-accent);
  font-size: 13px;
  font-weight: 750;
}

h1 {
  margin: 0;
  font-size: clamp(36px, 5vw, 58px);
  line-height: 1.12;
  text-wrap: balance;
}

header span {
  display: block;
  margin-top: 18px;
  color: var(--oa-muted);
  font-size: 19px;
}

.choice-grid {
  display: grid;
  max-width: 1180px;
  margin: 0 auto;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 24px;
}

.workflow-choice {
  position: relative;
  display: grid;
  min-height: 176px;
  border: 1px solid #cbd5e1;
  border-radius: 12px;
  padding: 24px;
  color: var(--oa-ink);
  background: rgb(255 255 255 / 72%);
  text-align: left;
  grid-template-rows: auto auto 1fr;
  gap: 8px;
  transition:
    transform 120ms ease-out,
    border-color 160ms ease-out,
    background-color 160ms ease-out,
    box-shadow 160ms ease-out;
}

.workflow-choice:active {
  transform: scale(0.98);
}

.workflow-choice.selected {
  border-color: #0b6ed0;
  background: #fff;
  box-shadow: 0 12px 28px rgb(15 23 42 / 7%);
}

.workflow-choice__kind {
  width: fit-content;
  border-radius: 6px;
  padding: 5px 7px;
  color: var(--oa-accent);
  background: #eaf3f8;
  font-size: 12px;
  font-weight: 800;
}

.workflow-choice strong {
  margin-top: 8px;
  font-size: 21px;
}

.workflow-choice small {
  color: var(--oa-muted);
  font-size: 15px;
  line-height: 1.6;
}

.selected-mark {
  position: absolute;
  top: 16px;
  right: 16px;
  color: #0b6ed0;
  font-size: 13px;
  font-weight: 700;
}

.continue-button {
  display: block;
  min-width: 210px;
  margin: 40px auto 62px;
}

.recent-section {
  max-width: 1180px;
  margin: 0 auto;
  padding-top: 28px;
  border-top: 1px solid var(--oa-line);
}

.recent-section > div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

h2 {
  margin: 0;
  font-size: 22px;
}

.recent-section p {
  margin: 16px 0 0;
  color: var(--oa-muted);
  line-height: 1.7;
}

@media (max-width: 820px) {
  .choice-grid {
    grid-template-columns: 1fr;
  }

  .workflow-choice {
    min-height: 148px;
  }

  header {
    text-align: left;
  }

  .continue-button {
    width: auto;
    margin-left: 0;
  }
}
</style>
