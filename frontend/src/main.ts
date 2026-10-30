import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import '@xterm/xterm/css/xterm.css'
import '@/styles/main.css'
import App from './App.vue'
import router from './router'
import { responsiveTable } from './directives/responsiveTable'

createApp(App).use(createPinia()).use(router).use(ElementPlus).directive('responsive-table', responsiveTable).mount('#app')
