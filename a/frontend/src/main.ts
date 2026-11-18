import { createApp, h } from 'vue'
import {
  ElAlert, ElButton, ElConfigProvider, ElDialog, ElDrawer, ElEmpty, ElIcon,
  ElInput, ElInputNumber, ElOption, ElProgress, ElSelect, ElSkeleton,
  ElTabPane, ElTabs, ElTag,
} from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import 'element-plus/dist/index.css'
import './style.css'
import App from './App.vue'

const app = createApp({ render: () => h(ElConfigProvider, { locale: zhCn }, { default: () => h(App) }) })
for (const component of [ElAlert, ElButton, ElDialog, ElDrawer, ElEmpty, ElIcon, ElInput,
  ElInputNumber, ElOption, ElProgress, ElSelect, ElSkeleton, ElTabPane, ElTabs, ElTag]) {
  app.use(component)
}
app.mount('#app')
