<script setup lang="ts">
import {
  Box,
  DataAnalysis,
  DataLine,
  Document,
  Files,
  House,
  Money,
  Operation,
  PieChart,
  Search,
  Setting,
  SwitchButton,
  User,
  Wallet,
} from '@element-plus/icons-vue'
import { ElMessageBox } from 'element-plus'
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const pageTitle = computed(() => String(route.meta.title ?? '工作台'))

async function handleLogout() {
  try {
    await ElMessageBox.confirm('确定退出新系统吗？', '退出登录', {
      confirmButtonText: '退出',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await auth.logout()
    await router.replace({ name: 'login' })
  } catch {
    // 用户取消时保持当前页面。
  }
}
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark"><Box /></div>
        <div class="brand-copy">
          <strong>毅播云仓</strong>
          <span>现代化管理平台</span>
        </div>
      </div>

      <div class="edition">NEW SYSTEM · V1.0</div>

      <ElMenu
        router
        :default-active="route.path"
        class="side-menu"
        background-color="transparent"
        text-color="#8fa4c4"
        active-text-color="#ffffff"
      >
        <ElMenuItem index="/">
          <ElIcon><House /></ElIcon>
          <span>工作台</span>
        </ElMenuItem>
        <ElMenuItem index="/analytics">
          <ElIcon><DataAnalysis /></ElIcon>
          <span>经营分析</span>
        </ElMenuItem>

        <div class="menu-section">业务模块</div>
        <ElSubMenu index="express">
          <template #title>
            <ElIcon><DataLine /></ElIcon>
            <span>快递对账</span>
          </template>
          <ElMenuItem index="/express"><ElIcon><House /></ElIcon><span>看板</span></ElMenuItem>
          <ElMenuItem index="/express/run"><ElIcon><Operation /></ElIcon><span>运行</span></ElMenuItem>
          <ElMenuItem index="/express/history"><ElIcon><Files /></ElIcon><span>历史</span></ElMenuItem>
          <ElMenuItem index="/express/stats"><ElIcon><PieChart /></ElIcon><span>统计</span></ElMenuItem>
          <ElMenuItem index="/express/config"><ElIcon><Setting /></ElIcon><span>配置</span></ElMenuItem>
        </ElSubMenu>

        <ElSubMenu index="query">
          <template #title>
            <ElIcon><Search /></ElIcon>
            <span>数据查询</span>
          </template>
          <ElMenuItem index="/query"><ElIcon><Document /></ElIcon><span>查询导出</span></ElMenuItem>
        </ElSubMenu>

        <ElSubMenu index="finance">
          <template #title>
            <ElIcon><Money /></ElIcon>
            <span>财务模块</span>
          </template>
          <ElMenuItem index="/finance"><ElIcon><House /></ElIcon><span>模块首页</span></ElMenuItem>
          <ElMenuItem index="/salary"><ElIcon><Wallet /></ElIcon><span>员工工资</span></ElMenuItem>
          <ElMenuItem index="/reimbursement"><ElIcon><Document /></ElIcon><span>报销</span></ElMenuItem>
        </ElSubMenu>

        <ElMenuItem index="/storage">
          <ElIcon><Box /></ElIcon>
          <span>仓储费</span>
        </ElMenuItem>
      </ElMenu>

      <div class="sidebar-footer">
        <a href="http://127.0.0.1:5001" target="_blank" rel="noreferrer">
          <SwitchButton />
          <span>打开老系统（稳定版）</span>
        </a>
      </div>
    </aside>

    <section class="workspace">
      <header class="topbar">
        <div>
          <span class="breadcrumb">新系统</span>
          <h2>{{ pageTitle }}</h2>
        </div>
        <div class="account">
          <div class="account-avatar"><User /></div>
          <div class="account-copy">
            <strong>{{ auth.user?.display_name }}</strong>
            <span>{{ auth.user?.role === 'admin' ? '系统管理员' : auth.user?.role }}</span>
          </div>
          <ElButton text :icon="SwitchButton" @click="handleLogout">退出</ElButton>
        </div>
      </header>

      <main class="content">
        <RouterView />
      </main>
    </section>
  </div>
</template>

<style scoped>
.app-shell {
  display: flex;
  min-height: 100vh;
  background: #f3f6fb;
}

.sidebar {
  position: fixed;
  z-index: 10;
  display: flex;
  flex-direction: column;
  width: 248px;
  height: 100vh;
  padding: 24px 15px 18px;
  overflow: hidden;
  color: #fff;
  background:
    radial-gradient(circle at 0 0, rgba(47, 111, 235, 0.22), transparent 34%),
    linear-gradient(180deg, #132b50 0%, #0b1b34 100%);
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 10px;
}

.brand-mark {
  display: grid;
  width: 39px;
  height: 39px;
  flex: 0 0 auto;
  place-items: center;
  border: 1px solid rgba(255, 255, 255, 0.18);
  border-radius: 12px;
  background: linear-gradient(145deg, #3b82f6, #1e5fc4);
  box-shadow: 0 8px 20px rgba(19, 91, 208, 0.35);
}

.brand-mark :deep(svg) {
  width: 21px;
}

.brand-copy {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.brand-copy strong {
  font-size: 18px;
  letter-spacing: 0.08em;
}

.brand-copy span {
  margin-top: 3px;
  color: #8fa4c4;
  font-size: 11px;
}

.edition {
  align-self: flex-start;
  margin: 22px 10px 13px;
  padding: 4px 8px;
  border: 1px solid rgba(91, 192, 222, 0.24);
  border-radius: 6px;
  color: #7dd3e0;
  background: rgba(24, 139, 166, 0.12);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.side-menu {
  flex: 1;
  border-right: 0;
}

.side-menu :deep(.el-menu-item) {
  height: 46px;
  margin: 4px 0;
  border-radius: 9px;
  font-size: 14px;
}

.side-menu :deep(.el-sub-menu__title) {
  height: 46px;
  margin: 4px 0;
  border-radius: 9px;
  font-size: 14px;
}

.side-menu :deep(.el-sub-menu__title:hover) {
  background: rgba(255, 255, 255, 0.06);
}

.side-menu :deep(.el-sub-menu .el-menu-item) {
  min-width: 0;
  padding-left: 45px !important;
  background: transparent;
  font-size: 13px;
}

.side-menu :deep(.el-menu-item:hover) {
  background: rgba(255, 255, 255, 0.06);
}

.side-menu :deep(.el-menu-item.is-active) {
  background: linear-gradient(90deg, #2869d1, #2456a0);
  box-shadow: 0 8px 18px rgba(12, 69, 158, 0.26);
}

.menu-section {
  padding: 21px 14px 5px;
  color: #637b9e;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
}

.sidebar-footer a {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 12px 14px;
  border: 1px solid rgba(255, 255, 255, 0.09);
  border-radius: 10px;
  color: #aec0da;
  background: rgba(255, 255, 255, 0.035);
  font-size: 13px;
  text-decoration: none;
  transition: 0.2s ease;
}

.sidebar-footer a:hover {
  border-color: rgba(91, 160, 255, 0.35);
  color: #fff;
  background: rgba(47, 111, 235, 0.12);
}

.sidebar-footer svg {
  width: 17px;
}

.workspace {
  width: calc(100% - 248px);
  min-height: 100vh;
  margin-left: 248px;
}

.topbar {
  position: sticky;
  top: 0;
  z-index: 8;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 76px;
  padding: 0 32px;
  border-bottom: 1px solid #e8edf5;
  background: rgba(255, 255, 255, 0.94);
  backdrop-filter: blur(10px);
}

.topbar h2 {
  margin: 2px 0 0;
  color: #16223a;
  font-size: 18px;
}

.breadcrumb {
  color: #8793a7;
  font-size: 11px;
}

.account {
  display: flex;
  align-items: center;
  gap: 10px;
}

.account-avatar {
  display: grid;
  width: 34px;
  height: 34px;
  place-items: center;
  border-radius: 10px;
  color: #2f6feb;
  background: #eaf1ff;
}

.account-avatar svg {
  width: 18px;
}

.account-copy {
  display: flex;
  min-width: 88px;
  flex-direction: column;
}

.account-copy strong {
  color: #27344d;
  font-size: 13px;
}

.account-copy span {
  margin-top: 2px;
  color: #8b97a9;
  font-size: 11px;
}

.content {
  max-width: 1600px;
  min-height: calc(100vh - 76px);
  padding: 28px 32px 44px;
}

@media (max-width: 820px) {
  .sidebar {
    width: 78px;
    padding-right: 10px;
    padding-left: 10px;
  }

  .brand {
    justify-content: center;
    padding: 0;
  }

  .brand-copy,
  .edition,
  .menu-section,
  .side-menu :deep(.el-menu-item span),
  .sidebar-footer span,
  .account-copy {
    display: none;
  }

  .side-menu :deep(.el-menu-item) {
    justify-content: center;
    padding: 0 !important;
  }

  .sidebar-footer a {
    justify-content: center;
  }

  .workspace {
    width: calc(100% - 78px);
    margin-left: 78px;
  }

  .topbar,
  .content {
    padding-right: 18px;
    padding-left: 18px;
  }
}
</style>
