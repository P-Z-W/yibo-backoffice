<script setup lang="ts">
import {
  CircleCheck,
  CircleClose,
  Edit,
  Key,
  Lock,
  Plus,
  Refresh,
  Search,
  Setting,
  UserFilled,
  View,
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, reactive, ref, watch } from 'vue'
import {
  createRole,
  createUser,
  deleteRole,
  getAccessOverview,
  getAuditLogs,
  getPermissions,
  getRoles,
  getUsers,
  resetUserPassword,
  updateRole,
  updateUser,
  type AccessOverview,
  type AuditEntry,
  type ManagedUser,
  type PermissionDefinition,
  type RoleDefinition,
  type RolePayload,
  type UserPayload,
} from '../api/access'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const activeTab = ref('accounts')
const loading = ref(false)
const overview = ref<AccessOverview>({
  summary: { total: 0, active: 0, disabled: 0, administrators: 0 },
  teams: [],
})
const users = ref<ManagedUser[]>([])
const roles = ref<RoleDefinition[]>([])
const permissions = ref<PermissionDefinition[]>([])
const auditLogs = ref<AuditEntry[]>([])

const filters = reactive({ keyword: '', role: '', team: '', active: '' })
const auditFilters = reactive({ keyword: '', action: '' })
const userDialog = ref(false)
const userSaving = ref(false)
const editingUserId = ref<number | null>(null)
const userForm = reactive({
  display_name: '',
  team: '',
  roles: ['employee'] as string[],
  is_active: true,
})
const userFormSnapshot = ref('')

const selectedRoleCode = ref('')
const roleSaving = ref(false)
const roleDraft = reactive<RolePayload>({ name: '', description: '', permissions: {} })
const newRoleDialog = ref(false)
const newRoleForm = reactive({ name: '', description: '' })

const selectedRole = computed(() => roles.value.find((item) => item.code === selectedRoleCode.value))
const userFormDirty = computed(
  () => userDialog.value && serializeUserForm() !== userFormSnapshot.value,
)
const permissionGroups = computed(() => {
  const groups = new Map<string, PermissionDefinition[]>()
  for (const item of permissions.value) {
    const group = groups.get(item.module) || []
    group.push(item)
    groups.set(item.module, group)
  }
  return [...groups.entries()].map(([module, items]) => ({ module, items }))
})

function errorText(error: any, fallback: string) {
  return error?.response?.data?.detail || fallback
}

function formatTime(value: string | null) {
  if (!value) return '从未登录'
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}

function roleType(code: string) {
  if (code === 'admin') return 'danger'
  if (code === 'finance') return 'warning'
  if (code === 'supervisor') return 'success'
  if (code === 'team_leader') return 'primary'
  return 'info'
}

function serializeUserForm() {
  return JSON.stringify({
    display_name: userForm.display_name,
    team: userForm.team,
    roles: [...userForm.roles],
    is_active: userForm.is_active,
  })
}

function rememberUserForm() {
  userFormSnapshot.value = serializeUserForm()
}

async function confirmDiscardUserChanges() {
  if (!userFormDirty.value) return true
  try {
    await ElMessageBox.confirm(
      '当前账号信息尚未保存，确定要取消并放弃修改吗？',
      '尚未保存',
      {
        type: 'warning',
        confirmButtonText: '放弃修改',
        cancelButtonText: '继续编辑',
      },
    )
    return true
  } catch {
    return false
  }
}

async function cancelUserDialog() {
  if (await confirmDiscardUserChanges()) userDialog.value = false
}

async function beforeUserDialogClose(done: () => void) {
  if (await confirmDiscardUserChanges()) done()
}

async function loadAccounts() {
  const params: Record<string, string | boolean | undefined> = {
    keyword: filters.keyword || undefined,
    role: filters.role || undefined,
    team: filters.team || undefined,
    active: filters.active === '' ? undefined : filters.active === 'true',
  }
  ;[overview.value, users.value] = await Promise.all([getAccessOverview(), getUsers(params)])
}

async function loadRoles() {
  if (!auth.can('roles.view')) return
  ;[roles.value, permissions.value] = await Promise.all([getRoles(), getPermissions()])
  if (!roles.value.some((item) => item.code === selectedRoleCode.value)) {
    selectedRoleCode.value = roles.value[0]?.code || ''
  } else {
    selectRole(selectedRoleCode.value)
  }
}

async function loadAll() {
  loading.value = true
  try {
    await Promise.all([loadAccounts(), loadRoles()])
  } catch (error: any) {
    ElMessage.error(errorText(error, '账号权限数据加载失败'))
  } finally {
    loading.value = false
  }
}

async function loadAudit() {
  if (!auth.can('audit.view')) return
  try {
    auditLogs.value = await getAuditLogs({
      keyword: auditFilters.keyword || undefined,
      action: auditFilters.action || undefined,
      limit: 200,
    })
  } catch (error: any) {
    ElMessage.error(errorText(error, '操作日志加载失败'))
  }
}

function openCreateUser() {
  editingUserId.value = null
  Object.assign(userForm, {
    display_name: '',
    team: overview.value.teams[0] || '',
    roles: ['employee'],
    is_active: true,
  })
  rememberUserForm()
  userDialog.value = true
}

function openEditUser(row: ManagedUser) {
  editingUserId.value = row.id
  Object.assign(userForm, {
    display_name: row.display_name,
    team: row.team,
    roles: [...row.roles],
    is_active: row.is_active,
  })
  rememberUserForm()
  userDialog.value = true
}

async function submitUser() {
  if (!userForm.display_name.trim() || !userForm.roles.length) {
    ElMessage.warning('请填写姓名并至少选择一个岗位角色')
    return
  }
  userSaving.value = true
  try {
    const payload: UserPayload = {
      display_name: userForm.display_name.trim(),
      team: userForm.team.trim(),
      roles: [...userForm.roles],
      is_active: userForm.is_active,
    }
    if (editingUserId.value) {
      await updateUser(editingUserId.value, payload)
      ElMessage.success('账号信息已保存')
    } else {
      await createUser(payload)
      ElMessage.success('账号已创建，默认密码为 423766')
    }
    rememberUserForm()
    userDialog.value = false
    await Promise.all([loadAccounts(), loadRoles()])
  } catch (error: any) {
    ElMessage.error(errorText(error, '账号保存失败'))
  } finally {
    userSaving.value = false
  }
}

async function toggleUser(row: ManagedUser) {
  const action = row.is_active ? '停用' : '启用'
  try {
    await ElMessageBox.confirm(
      row.is_active
        ? `停用后“${row.display_name}”将立即无法继续使用系统。`
        : `确定重新启用“${row.display_name}”吗？`,
      `${action}账号`,
      { type: row.is_active ? 'warning' : 'info', confirmButtonText: action },
    )
    await updateUser(row.id, {
      display_name: row.display_name,
      team: row.team,
      roles: [...row.roles],
      is_active: !row.is_active,
    })
    ElMessage.success(`账号已${action}`)
    await loadAccounts()
  } catch (error: any) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(errorText(error, `${action}失败`))
  }
}

async function resetPassword(row: ManagedUser) {
  try {
    await ElMessageBox.confirm(
      `将“${row.display_name}”的密码重置为默认密码 423766，旧密码立即失效。`,
      '重置密码',
      { type: 'warning', confirmButtonText: '重置密码' },
    )
    await resetUserPassword(row.id)
    ElMessage.success('密码已重置为 423766')
    await Promise.all([loadAccounts(), loadAudit()])
  } catch (error: any) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(errorText(error, '重置密码失败'))
  }
}

function selectRole(code: string) {
  selectedRoleCode.value = code
  const role = roles.value.find((item) => item.code === code)
  if (!role) return
  roleDraft.name = role.name
  roleDraft.description = role.description
  roleDraft.permissions = { ...role.permissions }
}

function setPermission(code: string, checked: boolean) {
  if (checked) roleDraft.permissions[code] = 'all'
  else delete roleDraft.permissions[code]
}

async function saveRole() {
  const role = selectedRole.value
  if (!role || role.code === 'admin') return
  roleSaving.value = true
  try {
    await updateRole(role.code, {
      name: roleDraft.name.trim(),
      description: roleDraft.description.trim(),
      permissions: { ...roleDraft.permissions },
    })
    ElMessage.success('角色权限已生效')
    await Promise.all([loadRoles(), auth.loadCurrentUser()])
  } catch (error: any) {
    ElMessage.error(errorText(error, '角色保存失败'))
  } finally {
    roleSaving.value = false
  }
}

async function submitNewRole() {
  if (newRoleForm.name.trim().length < 2) {
    ElMessage.warning('请输入至少两个字的角色名称')
    return
  }
  try {
    const result = await createRole({
      name: newRoleForm.name.trim(),
      description: newRoleForm.description.trim(),
      permissions: { 'dashboard.view': 'all' },
    })
    newRoleDialog.value = false
    Object.assign(newRoleForm, { name: '', description: '' })
    await loadRoles()
    selectRole(result.code)
    ElMessage.success('角色已创建，请继续配置权限')
  } catch (error: any) {
    ElMessage.error(errorText(error, '角色创建失败'))
  }
}

async function removeRole() {
  const role = selectedRole.value
  if (!role || role.is_system) return
  try {
    await ElMessageBox.confirm(`确定删除角色“${role.name}”吗？`, '删除角色', {
      type: 'warning',
      confirmButtonText: '删除',
    })
    await deleteRole(role.code)
    ElMessage.success('角色已删除')
    selectedRoleCode.value = ''
    await loadRoles()
  } catch (error: any) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(errorText(error, '角色删除失败'))
  }
}

const actionLabels: Record<string, string> = {
  login: '登录系统',
  login_failed: '登录失败',
  logout: '退出系统',
  user_create: '创建账号',
  user_update: '修改账号',
  password_reset: '重置密码',
  password_change: '修改密码',
  role_create: '创建角色',
  role_update: '修改角色权限',
  role_delete: '删除角色',
}

function detailText(row: AuditEntry) {
  if (!row.detail) return '—'
  try {
    const value = JSON.parse(row.detail)
    return [value.target_name, value.username].filter(Boolean).join(' · ') || row.resource
  } catch {
    return row.detail
  }
}

watch(activeTab, (value) => {
  if (value === 'audit' && !auditLogs.value.length) void loadAudit()
})
watch(selectedRoleCode, (value) => {
  if (value) selectRole(value)
})

onMounted(loadAll)
</script>

<template>
  <div v-loading="loading" class="access-page">
    <header class="page-heading">
      <div>
        <h1>账号与权限</h1>
        <p>统一管理人员账号、岗位角色和授权变更记录。</p>
      </div>
      <ElButton :icon="Refresh" @click="loadAll">刷新</ElButton>
    </header>

    <section class="summary-grid">
      <article class="surface-card summary-card">
        <span class="summary-icon blue"><UserFilled /></span>
        <div><small>全部账号</small><strong>{{ overview.summary.total }}</strong><p>约 30 人轻量管理</p></div>
      </article>
      <article class="surface-card summary-card">
        <span class="summary-icon green"><CircleCheck /></span>
        <div><small>正常使用</small><strong>{{ overview.summary.active }}</strong><p>当前有效账号</p></div>
      </article>
      <article class="surface-card summary-card">
        <span class="summary-icon gray"><CircleClose /></span>
        <div><small>已停用</small><strong>{{ overview.summary.disabled }}</strong><p>历史记录仍保留</p></div>
      </article>
      <article class="surface-card summary-card">
        <span class="summary-icon orange"><Lock /></span>
        <div><small>系统管理员</small><strong>{{ overview.summary.administrators }}</strong><p>建议一主一备</p></div>
      </article>
    </section>

    <section class="surface-card main-card">
      <ElTabs v-model="activeTab" class="access-tabs">
        <ElTabPane label="账号管理" name="accounts">
          <div class="toolbar">
            <div class="filters">
              <ElInput v-model="filters.keyword" :prefix-icon="Search" clearable placeholder="姓名" @keyup.enter="loadAccounts" />
              <ElSelect v-model="filters.role" clearable placeholder="全部角色">
                <ElOption v-for="role in roles" :key="role.code" :label="role.name" :value="role.code" />
              </ElSelect>
              <ElSelect v-model="filters.team" clearable placeholder="全部组别">
                <ElOption v-for="team in overview.teams" :key="team" :label="team" :value="team" />
              </ElSelect>
              <ElSelect v-model="filters.active" placeholder="全部状态">
                <ElOption label="全部状态" value="" />
                <ElOption label="正常使用" value="true" />
                <ElOption label="已停用" value="false" />
              </ElSelect>
              <ElButton :icon="Search" @click="loadAccounts">筛选</ElButton>
            </div>
            <ElButton v-if="auth.can('accounts.manage')" type="primary" :icon="Plus" @click="openCreateUser">新建账号</ElButton>
          </div>

          <ElTable :data="users" class="data-table">
            <ElTableColumn label="人员" min-width="190">
              <template #default="{ row }">
                <div class="person-cell">
                  <span class="person-avatar">{{ row.display_name.slice(0, 1) }}</span>
                  <div><strong>{{ row.display_name }}</strong></div>
                </div>
              </template>
            </ElTableColumn>
            <ElTableColumn label="岗位角色" min-width="210">
              <template #default="{ row }"><div class="role-tags"><ElTag v-for="(name, index) in row.role_names" :key="row.roles[index]" :type="roleType(row.roles[index])" effect="light">{{ name }}</ElTag></div></template>
            </ElTableColumn>
            <ElTableColumn prop="team" label="所属组" width="120"><template #default="{ row }">{{ row.team || '未分组' }}</template></ElTableColumn>
            <ElTableColumn label="状态" width="110">
              <template #default="{ row }"><span :class="['status-dot', row.is_active ? 'active' : 'disabled']">{{ row.is_active ? '正常' : '已停用' }}</span></template>
            </ElTableColumn>
            <ElTableColumn label="密码状态" width="120">
              <template #default="{ row }"><span :class="{ warning: row.must_change_password }">{{ row.must_change_password ? '使用默认密码' : '正常' }}</span></template>
            </ElTableColumn>
            <ElTableColumn label="最新密码" width="150">
              <template #default="{ row }"><code class="latest-password">{{ row.latest_password || '未记录' }}</code></template>
            </ElTableColumn>
            <ElTableColumn label="最后登录" min-width="180"><template #default="{ row }">{{ formatTime(row.last_login_at) }}</template></ElTableColumn>
            <ElTableColumn v-if="auth.can('accounts.manage')" label="操作" width="230" fixed="right">
              <template #default="{ row }">
                <ElButton text type="primary" :icon="Edit" @click="openEditUser(row)">编辑</ElButton>
                <ElButton text :icon="Key" :disabled="row.id === auth.user?.id" @click="resetPassword(row)">重置密码</ElButton>
                <ElButton text :type="row.is_active ? 'danger' : 'success'" :disabled="row.id === auth.user?.id" @click="toggleUser(row)">{{ row.is_active ? '停用' : '启用' }}</ElButton>
              </template>
            </ElTableColumn>
          </ElTable>
          <ElEmpty v-if="!users.length" description="没有符合条件的账号" />
        </ElTabPane>

        <ElTabPane v-if="auth.can('roles.view')" label="角色权限" name="roles">
          <div class="role-layout">
            <aside class="role-list">
              <div class="role-list-head"><strong>岗位角色</strong><ElButton v-if="auth.can('roles.manage')" text type="primary" :icon="Plus" @click="newRoleDialog = true">新建</ElButton></div>
              <button v-for="role in roles" :key="role.code" :class="['role-item', { active: selectedRoleCode === role.code }]" @click="selectRole(role.code)">
                <span class="role-symbol"><Setting /></span>
                <span><strong>{{ role.name }}</strong><small>{{ role.user_count }} 个账号 · {{ Object.keys(role.permissions).length }} 项权限</small></span>
                <ElTag v-if="role.is_system" size="small" effect="plain">预设</ElTag>
              </button>
            </aside>

            <div v-if="selectedRole" class="role-editor">
              <div class="role-editor-head">
                <div><span>角色设置</span><h3>{{ selectedRole.name }}</h3></div>
                <div>
                  <ElButton v-if="!selectedRole.is_system && auth.can('roles.manage')" type="danger" plain @click="removeRole">删除角色</ElButton>
                  <ElButton v-if="selectedRole.code !== 'admin' && auth.can('roles.manage')" type="primary" :loading="roleSaving" @click="saveRole">保存更改</ElButton>
                </div>
              </div>
              <ElAlert v-if="selectedRole.code === 'admin'" title="系统管理员权限固定为全量，不能修改。" type="warning" :closable="false" show-icon />
              <div class="role-meta">
                <ElInput v-model="roleDraft.name" :disabled="selectedRole.code === 'admin' || !auth.can('roles.manage')" placeholder="角色名称" />
                <ElInput v-model="roleDraft.description" :disabled="selectedRole.code === 'admin' || !auth.can('roles.manage')" placeholder="角色说明" />
              </div>
              <div class="permission-head"><strong>功能权限</strong><span>勾选岗位需要使用的功能；涉及业务数据时可限制查看范围。</span></div>
              <section v-for="group in permissionGroups" :key="group.module" class="permission-group">
                <h4>{{ group.module }}</h4>
                <div class="permission-list">
                  <div v-for="item in group.items" :key="item.code" class="permission-row">
                    <ElCheckbox :model-value="Boolean(roleDraft.permissions[item.code])" :disabled="selectedRole.code === 'admin' || !auth.can('roles.manage')" @change="setPermission(item.code, Boolean($event))">
                      <span><strong>{{ item.action }}</strong><small>{{ item.name }}</small></span>
                    </ElCheckbox>
                    <ElSelect v-if="item.supports_scope && roleDraft.permissions[item.code]" v-model="roleDraft.permissions[item.code]" :disabled="selectedRole.code === 'admin' || !auth.can('roles.manage')" size="small">
                      <ElOption label="仅本人" value="self" />
                      <ElOption label="本组" value="team" />
                      <ElOption label="全部" value="all" />
                    </ElSelect>
                  </div>
                </div>
              </section>
            </div>
          </div>
        </ElTabPane>

        <ElTabPane v-if="auth.can('audit.view')" label="操作日志" name="audit">
          <div class="toolbar">
            <div class="filters">
              <ElInput v-model="auditFilters.keyword" :prefix-icon="Search" clearable placeholder="人员、账号或对象" @keyup.enter="loadAudit" />
              <ElSelect v-model="auditFilters.action" clearable placeholder="全部操作">
                <ElOption v-for="(label, value) in actionLabels" :key="value" :label="label" :value="value" />
              </ElSelect>
              <ElButton :icon="Search" @click="loadAudit">筛选</ElButton>
            </div>
          </div>
          <ElTable :data="auditLogs" class="data-table">
            <ElTableColumn prop="operator_name" label="操作者" width="140" />
            <ElTableColumn label="操作" width="150"><template #default="{ row }"><ElTag effect="plain">{{ actionLabels[row.action] || row.action }}</ElTag></template></ElTableColumn>
            <ElTableColumn label="对象/摘要" min-width="220"><template #default="{ row }">{{ detailText(row) }}</template></ElTableColumn>
            <ElTableColumn prop="ip_address" label="IP 地址" width="150" />
            <ElTableColumn label="时间" width="190"><template #default="{ row }">{{ formatTime(row.created_at) }}</template></ElTableColumn>
            <ElTableColumn label="详情" width="90"><template #default="{ row }"><ElTooltip :content="row.detail || row.resource" placement="left"><ElButton text :icon="View" /></ElTooltip></template></ElTableColumn>
          </ElTable>
          <ElEmpty v-if="!auditLogs.length" description="暂无操作记录" />
        </ElTabPane>
      </ElTabs>
    </section>

    <ElDialog v-model="userDialog" :title="editingUserId ? '编辑账号' : '新建账号'" width="560px" :before-close="beforeUserDialogClose">
      <ElForm label-position="top">
        <div class="form-grid">
          <ElFormItem label="姓名"><ElInput v-model="userForm.display_name" placeholder="人员真实姓名" /></ElFormItem>
          <ElFormItem label="所属组"><ElSelect v-model="userForm.team" filterable allow-create default-first-option placeholder="选择或输入组别"><ElOption v-for="team in overview.teams" :key="team" :label="team" :value="team" /></ElSelect></ElFormItem>
          <ElFormItem class="full-span" label="岗位角色（可多选）"><ElSelect v-model="userForm.roles" multiple collapse-tags collapse-tags-tooltip :max-collapse-tags="2" placeholder="至少选择一个岗位角色"><ElOption v-for="role in roles" :key="role.code" :label="role.name" :value="role.code" /></ElSelect></ElFormItem>
        </div>
        <ElFormItem v-if="editingUserId" label="账号状态"><ElSwitch v-model="userForm.is_active" active-text="正常使用" inactive-text="已停用" :disabled="editingUserId === auth.user?.id" /></ElFormItem>
        <ElAlert class="form-alert" title="多个角色的权限会自动合并；同一权限的数据范围取本人、本组、全部中的最大范围。" type="success" :closable="false" show-icon />
        <ElAlert v-if="!editingUserId" class="form-alert" title="默认密码为 423766；首次登录可直接使用，第二次登录仍未修改时会提醒修改。" type="info" :closable="false" show-icon />
      </ElForm>
      <template #footer><ElButton @click="cancelUserDialog">取消</ElButton><ElButton type="primary" :loading="userSaving" @click="submitUser">保存</ElButton></template>
    </ElDialog>

    <ElDialog v-model="newRoleDialog" title="新建自定义角色" width="520px">
      <ElForm label-position="top">
        <ElFormItem label="角色名称"><ElInput v-model="newRoleForm.name" placeholder="例如：财务主管" /></ElFormItem>
        <ElFormItem label="角色说明"><ElInput v-model="newRoleForm.description" type="textarea" :rows="3" placeholder="说明这个岗位的职责范围" /></ElFormItem>
      </ElForm>
      <template #footer><ElButton @click="newRoleDialog = false">取消</ElButton><ElButton type="primary" @click="submitNewRole">创建并配置权限</ElButton></template>
    </ElDialog>
  </div>
</template>

<style scoped>
.access-page { min-height:500px; }
.summary-grid { display:grid; margin-bottom:20px; gap:16px; grid-template-columns:repeat(4,1fr); }
.summary-card { display:flex; align-items:center; min-height:112px; padding:20px; gap:15px; }
.summary-icon { display:grid; width:48px; height:48px; flex:0 0 auto; place-items:center; border-radius:15px; }
.summary-icon :deep(svg) { width:22px; }
.summary-icon.blue { color:#2f6feb; background:#eaf1ff; }.summary-icon.green { color:#18a36b; background:#e8f8f1; }.summary-icon.gray { color:#748196; background:#eef1f5; }.summary-icon.orange { color:#df7a18; background:#fff1df; }
.summary-card div { display:grid; grid-template-columns:auto 1fr; align-items:center; column-gap:12px; }
.summary-card small { color:#77849a; font-size:12px; }.summary-card strong { grid-row:span 2; font-size:30px; }.summary-card p { margin:5px 0 0; color:#a0a9b8; font-size:11px; }
.main-card { overflow:hidden; }.access-tabs :deep(.el-tabs__header) { margin:0; padding:0 24px; border-bottom:1px solid #e9edf3; }.access-tabs :deep(.el-tabs__nav-wrap::after) { display:none; }.access-tabs :deep(.el-tabs__content) { overflow:visible; }
.toolbar { display:flex; align-items:center; justify-content:space-between; padding:20px 24px; gap:16px; }.filters { display:flex; flex-wrap:wrap; gap:10px; }.filters .el-input { width:210px; }.filters .el-select { width:140px; }
.data-table { width:100%; }.data-table :deep(th.el-table__cell) { height:47px; color:#68758a; background:#f8fafc; font-size:12px; }.data-table :deep(td.el-table__cell) { height:60px; }
.person-cell { display:flex; align-items:center; gap:11px; }.person-avatar { display:grid; width:35px; height:35px; flex:0 0 auto; place-items:center; border-radius:11px; color:#2f6feb; background:#eaf1ff; font-weight:700; }.person-cell div { display:flex; flex-direction:column; }.person-cell strong { color:#27344d; font-size:13px; }.person-cell small { margin-top:3px; color:#98a2b2; }
.status-dot { display:inline-flex; align-items:center; gap:7px; }.status-dot::before { width:7px; height:7px; border-radius:50%; content:''; }.status-dot.active::before { background:#20ad74; box-shadow:0 0 0 4px #e5f7ef; }.status-dot.disabled { color:#8d98a9; }.status-dot.disabled::before { background:#aab3c1; }.warning { color:#df7a18; }
.latest-password { color:#245ba7; font-family:Consolas,monospace; font-size:13px; font-weight:700; }
.role-tags { display:flex; flex-wrap:wrap; gap:5px; }
.role-layout { display:grid; min-height:650px; grid-template-columns:280px 1fr; }.role-list { padding:18px 14px; border-right:1px solid #e8edf4; background:#fbfcfe; }.role-list-head { display:flex; align-items:center; justify-content:space-between; padding:0 8px 12px; }.role-item { display:grid; width:100%; margin:3px 0; padding:13px 10px; border:0; border-radius:10px; grid-template-columns:36px 1fr auto; align-items:center; gap:9px; color:#354259; background:transparent; text-align:left; cursor:pointer; }.role-item:hover { background:#f0f4fa; }.role-item.active { color:#1d5fc6; background:#eaf2ff; }.role-symbol { display:grid; width:34px; height:34px; place-items:center; border-radius:10px; color:#5d6b81; background:#fff; box-shadow:0 2px 9px rgba(33,54,86,.08); }.role-symbol :deep(svg) { width:17px; }.role-item span:nth-child(2) { display:flex; min-width:0; flex-direction:column; }.role-item strong { font-size:13px; }.role-item small { margin-top:4px; color:#929daf; font-size:10px; }
.role-editor { padding:25px 28px 36px; }.role-editor-head { display:flex; align-items:center; justify-content:space-between; margin-bottom:20px; }.role-editor-head span { color:#8a96a8; font-size:11px; }.role-editor-head h3 { margin:4px 0 0; font-size:20px; }.role-meta { display:grid; margin:20px 0 26px; gap:12px; grid-template-columns:220px 1fr; }.permission-head { display:flex; align-items:baseline; margin-bottom:14px; gap:12px; }.permission-head span { color:#8a96a8; font-size:12px; }.permission-group { margin-bottom:17px; border:1px solid #e7ebf2; border-radius:12px; overflow:hidden; }.permission-group h4 { margin:0; padding:11px 15px; border-bottom:1px solid #e8edf3; color:#40506a; background:#f7f9fc; font-size:12px; }.permission-list { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); }.permission-row { display:flex; min-height:58px; padding:10px 14px; border-right:1px solid #edf0f5; border-bottom:1px solid #edf0f5; align-items:center; justify-content:space-between; gap:12px; }.permission-row :deep(.el-checkbox__label) span { display:flex; flex-direction:column; }.permission-row strong { color:#34425a; font-size:12px; }.permission-row small { margin-top:2px; color:#98a2b2; font-size:10px; }.permission-row .el-select { width:90px; }
.form-grid { display:grid; gap:0 16px; grid-template-columns:1fr 1fr; }.form-grid .el-select { width:100%; }.form-grid .full-span { grid-column:1/-1; }
.form-alert + .form-alert { margin-top:10px; }
@media (max-width:1100px) { .summary-grid { grid-template-columns:repeat(2,1fr); }.role-layout { grid-template-columns:230px 1fr; }.permission-list { grid-template-columns:1fr; } }
@media (max-width:760px) { .summary-grid { grid-template-columns:1fr; }.toolbar { align-items:stretch; flex-direction:column; }.filters>* { width:100%!important; }.role-layout { grid-template-columns:1fr; }.role-list { border-right:0; border-bottom:1px solid #e8edf4; }.role-meta,.form-grid { grid-template-columns:1fr; } }
</style>
