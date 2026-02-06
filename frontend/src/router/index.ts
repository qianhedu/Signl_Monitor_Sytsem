import { createRouter, createWebHistory } from 'vue-router'
import Layout from '../components/Layout.vue'
import DkxView from '../views/DkxView.vue'
import MaView from '../views/MaView.vue'
import DkxBacktestView from '../views/DkxBacktestView.vue'
import MaBacktestView from '../views/MaBacktestView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      component: Layout,
      children: [
        {
          path: '',
          redirect: '/dkx'
        },
        {
          path: 'dkx',
          name: 'dkx',
          component: DkxView,
          meta: { title: 'DKX 信号检测' }
        },
        {
          path: 'dkx-backtest',
          name: 'dkx-backtest',
          component: DkxBacktestView,
          meta: { title: 'DKX 信号策略统计' }
        },
        {
          path: 'ma',
          name: 'ma',
          component: MaView,
          meta: { title: '双均线策略' }
        },
        {
          path: 'ma-backtest',
          name: 'ma-backtest',
          component: MaBacktestView,
          meta: { title: '双均线策略统计' }
        }
      ]
    }
  ]
})

export default router
