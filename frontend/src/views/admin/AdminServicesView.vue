<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessageBox } from 'element-plus'
import { Plus, RefreshCw, Trash2 } from '@lucide/vue'
import { api } from '@/api/client'
import type { Service, ServicePayload } from '@/api/types'
import { useAsyncData } from '@/composables/useAsyncData'
import PageHeader from '@/components/PageHeader.vue'
import DataState from '@/components/DataState.vue'

const { data, loading, loaded, error, load } = useAsyncData(api.adminServices, [])
const dialogOpen = ref(false)
const saving = ref(false)
const busy = ref('')
const editingId = ref<string | null>(null)
const actionError = ref('')
const actionMessage = ref('')
const form = reactive({
  code: '',
  name: '',
  service_no: 1,
  protocol: 'TCP' as 'TCP' | 'HTTP',
  internal_port: 80,
  public_base_port: 20000,
  flag_path: '/data/flag',
  image: '',
  check_config: '{}',
})

function nextServiceNo() {
  return Math.max(0, ...data.value.map(service => service.service_no)) + 1
}

function openCreate() {
  editingId.value = null
  Object.assign(form, {
    code: '',
    name: '',
    service_no: nextServiceNo(),
    protocol: 'TCP',
    internal_port: 80,
    public_base_port: 20000,
    flag_path: '/data/flag',
    image: '',
    check_config: '{}',
  })
  actionError.value = ''
  dialogOpen.value = true
}

function openEdit(service: Service) {
  editingId.value = service.id
  Object.assign(form, {
    code: service.code,
    name: service.name,
    service_no: service.service_no,
    protocol: service.protocol,
    internal_port: service.internal_port,
    public_base_port: service.public_base_port,
    flag_path: service.flag_path,
    image: service.image,
    check_config: JSON.stringify(service.check_config ?? {}, null, 2),
  })
  actionError.value = ''
  dialogOpen.value = true
}

async function save() {
  actionError.value = ''
  if (!form.code.trim() || !form.name.trim() || !form.image.trim()) {
    actionError.value = '请填写服务代码、名称和镜像。'
    return
  }
  if (!/^[a-z0-9-]+$/.test(form.code.trim())) {
    actionError.value = '服务代码只能包含小写字母、数字和连字符。'
    return
  }
  let checkConfig: Record<string, unknown>
  try {
    const parsed = JSON.parse(form.check_config || '{}')
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) throw new Error('不是对象')
    checkConfig = parsed as Record<string, unknown>
  } catch {
    actionError.value = '健康检查配置必须是 JSON 对象。'
    return
  }
  const payload: ServicePayload = {
    code: form.code.trim(),
    name: form.name.trim(),
    service_no: Number(form.service_no),
    protocol: form.protocol,
    internal_port: Number(form.internal_port),
    public_base_port: Number(form.public_base_port),
    flag_path: form.flag_path.trim() || '/data/flag',
    image: form.image.trim(),
    check_config: checkConfig,
  }
  saving.value = true
  try {
    if (editingId.value) await api.updateService(editingId.value, payload)
    else await api.createService(payload)
    dialogOpen.value = false
    actionMessage.value = editingId.value ? '服务模板已更新。' : '服务模板已创建，可在列表中预检镜像。'
    await load()
  } catch (cause) {
    actionError.value = cause instanceof Error ? cause.message : '保存失败。'
  } finally {
    saving.value = false
  }
}

async function pullImage(service: Service) {
  actionError.value = ''
  actionMessage.value = ''
  busy.value = service.id
  try {
    await api.pullServiceImage(service.id)
    actionMessage.value = `镜像已就绪：${service.image}`
  } catch (cause) {
    actionError.value = cause instanceof Error ? cause.message : '镜像预检失败。'
  } finally {
    busy.value = ''
  }
}

async function remove(service: Service) {
  try {
    await ElMessageBox.confirm(`删除服务模板 ${service.name}（${service.code}）？已有靶机实例的模板不能删除。`, '删除服务模板', { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' })
  } catch {
    return
  }
  actionError.value = ''
  busy.value = service.id
  try {
    await api.deleteService(service.id)
    actionMessage.value = '服务模板已删除。'
    await load()
  } catch (cause) {
    actionError.value = cause instanceof Error ? cause.message : '删除失败。'
  } finally {
    busy.value = ''
  }
}

onMounted(load)
</script>

<template>
  <PageHeader title="服务模板" description="每队每种服务只创建一个靶机实例；代码和编号创建后不可修改，镜像必须能从服务器拉取。">
    <template #actions>
      <button class="button button--secondary" type="button" :disabled="loading" @click="load"><RefreshCw :size="16" aria-hidden="true" />刷新</button>
      <button class="button button--primary" type="button" @click="openCreate"><Plus :size="16" aria-hidden="true" />新建模板</button>
    </template>
  </PageHeader>
  <p v-if="actionError" class="inline-error" role="alert">{{ actionError }}</p>
  <p v-if="actionMessage" class="inline-success" role="status">{{ actionMessage }}</p>
  <DataState :loading="loading" :loaded="loaded" :error="error" :empty="!data.length" empty-text="尚未配置服务模板。先创建服务模板并预检镜像，再到靶机管理初始化。" @retry="load">
    <template #empty-action><button class="button button--primary" type="button" @click="openCreate">新建服务模板</button></template>
    <div class="table-scroll" tabindex="0" role="region" aria-label="服务模板列表，窄屏可横向滚动">
      <table v-responsive-table class="data-table">
        <thead><tr><th>编号</th><th>服务</th><th>协议 / 端口</th><th>镜像</th><th>Flag 路径</th><th>公网基准端口</th><th class="action-cell">操作</th></tr></thead>
        <tbody>
          <tr v-for="service in data" :key="service.id">
            <td>{{ String(service.service_no).padStart(2, '0') }}</td>
            <td><strong>{{ service.name }}</strong><small class="cell-subtitle"><code>{{ service.code }}</code></small></td>
            <td>{{ service.protocol }}:{{ service.internal_port }}</td>
            <td><code>{{ service.image }}</code></td>
            <td><code>{{ service.flag_path }}</code></td>
            <td class="num">{{ service.public_base_port }}</td>
            <td class="action-cell"><div class="table-actions"><button class="button button--text" type="button" @click="openEdit(service)">编辑</button><button class="button button--text" type="button" :disabled="busy === service.id" @click="pullImage(service)"><RefreshCw :size="15" aria-hidden="true" />{{ busy === service.id ? '预检中' : '预检镜像' }}</button><button class="button button--text" type="button" :disabled="busy === service.id" @click="remove(service)"><Trash2 :size="15" aria-hidden="true" />删除</button></div></td>
          </tr>
        </tbody>
      </table>
    </div>
  </DataState>

  <el-dialog v-model="dialogOpen" :title="editingId ? '编辑服务模板' : '新建服务模板'" width="min(720px, 94vw)">
    <form class="dialog-form" @submit.prevent="save">
      <div class="form-grid">
        <div class="form-field"><label for="service-code">服务代码</label><input id="service-code" v-model="form.code" class="input" type="text" pattern="[a-z0-9-]+" :disabled="!!editingId" required /><p class="field-help">小写字母、数字、连字符，创建后不可修改。</p></div>
        <div class="form-field"><label for="service-no">服务编号</label><input id="service-no" v-model.number="form.service_no" class="input" type="number" min="1" max="99" :disabled="!!editingId" required /><p class="field-help">用于计算公网端口，创建后不可修改。</p></div>
      </div>
      <div class="form-field"><label for="service-name">服务名称</label><input id="service-name" v-model="form.name" class="input" type="text" maxlength="100" required /></div>
      <div class="form-grid">
        <div class="form-field"><label for="service-protocol">健康检查协议</label><select id="service-protocol" v-model="form.protocol" class="input"><option value="TCP">TCP</option><option value="HTTP">HTTP</option></select></div>
        <div class="form-field"><label for="service-internal-port">容器内部端口</label><input id="service-internal-port" v-model.number="form.internal_port" class="input" type="number" min="1" max="65535" required /></div>
      </div>
      <div class="form-grid">
        <div class="form-field"><label for="service-public-port">公网基准端口</label><input id="service-public-port" v-model.number="form.public_base_port" class="input" type="number" min="1" max="65535" required /><p class="field-help">仅记录用；实际公网端口按“20000 + 队伍编号 × 100 + 服务编号”计算。</p></div>
        <div class="form-field"><label for="service-flag-path">容器内 Flag 路径</label><input id="service-flag-path" v-model="form.flag_path" class="input" type="text" maxlength="255" required /></div>
      </div>
      <div class="form-field"><label for="service-image">镜像</label><input id="service-image" v-model="form.image" class="input" type="text" maxlength="255" placeholder="registry.example.com/team/web:1.0" required /><p class="field-help">必须可从本机 Docker 拉取；保存后可点“预检镜像”。</p></div>
      <div class="form-field"><label for="service-check-config">健康检查配置（JSON）</label><textarea id="service-check-config" v-model="form.check_config" class="input textarea" rows="4" spellcheck="false" /><p class="field-help">HTTP 示例：{"path":"/","status":200}；TCP 可留空对象 {}。</p></div>
      <div class="dialog-actions"><button class="button button--secondary" type="button" @click="dialogOpen = false">取消</button><button class="button button--primary" type="submit" :disabled="saving">{{ saving ? '保存中' : '保存模板' }}</button></div>
    </form>
  </el-dialog>
</template>
