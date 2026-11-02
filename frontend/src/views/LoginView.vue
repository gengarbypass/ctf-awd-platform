<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { KeyRound, ShieldCheck, UserRound } from '@lucide/vue'
import { isDemo } from '@/api/client'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const username = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')

function fillDemo(role: 'PLAYER' | 'ADMIN') {
  username.value = role === 'ADMIN' ? 'admin' : 'player1'
  password.value = role === 'ADMIN' ? 'Admin123!' : 'Player123!'
  error.value = ''
}
async function submit() {
  error.value = ''
  if (!username.value.trim() || !password.value) { error.value = '请完整填写登录信息。'; return }
  loading.value = true
  try {
    await auth.login({ username: username.value.trim(), password: password.value })
    const requested = typeof route.query.redirect === 'string' && route.query.redirect.startsWith('/') ? route.query.redirect : auth.home()
    await router.replace(requested)
  } catch (cause) { error.value = cause instanceof Error ? cause.message : '登录失败，请重试。' } finally { loading.value = false }
}
</script>

<template>
  <div class="login-layout">
    <section class="login-intro">
      <div class="login-brand"><img class="brand__mark brand__mark--avatar" src="/taru-cyber-logo.png" alt="塔里木大学网络安全学院" /><span><strong>塔大网安</strong><small>师市行实战平台</small></span></div>
      <div class="login-intro__body"><h1>筑牢边疆数字防线、<br />锻造基层网安尖兵</h1></div>
      <dl class="login-rules"><div><dt>Flag 轮换</dt><dd>300 秒</dd></div><div><dt>提交宽限</dt><dd>30 秒</dd></div><div><dt>有效攻击</dt><dd>+100 / -50</dd></div></dl>
      <p class="login-access"><ShieldCheck :size="17" aria-hidden="true" />平台仅用于授权训练，所有关键操作保留审计记录。</p>
    </section>
    <section class="login-panel" aria-label="账号登录">
      <div class="login-form-wrap">
        <div class="login-form-heading"><h2>账号登录</h2><p>使用管理员分配的账号进入平台</p></div>
        <form class="login-form" @submit.prevent="submit">
          <div class="form-field"><label for="username">用户名</label><div class="input-with-icon"><UserRound :size="17" aria-hidden="true" /><input id="username" v-model="username" class="input" name="username" type="text" autocomplete="username" required @input="error = ''" /></div></div>
          <div class="form-field"><label for="password">密码</label><div class="input-with-icon"><KeyRound :size="17" aria-hidden="true" /><input id="password" v-model="password" class="input" name="password" type="password" autocomplete="current-password" required @input="error = ''" /></div></div>
          <p class="login-error" role="alert" aria-live="polite">{{ error }}</p>
          <button class="button button--primary login-submit" type="submit" :disabled="loading" :aria-busy="loading">{{ loading ? '正在验证' : '登录平台' }}</button>
        </form>
        <div v-if="isDemo" class="demo-accounts"><p>本地演示账号</p><div><button class="button button--secondary" type="button" @click="fillDemo('PLAYER')">填入选手账号</button><button class="button button--secondary" type="button" @click="fillDemo('ADMIN')">填入管理员账号</button></div><small>player1 / Player123!　 admin / Admin123!</small></div>
        <p class="login-help">无法登录或需要调整队伍，请联系比赛管理员。</p>
      </div>
    </section>
  </div>
</template>
