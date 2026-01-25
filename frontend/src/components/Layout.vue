<script setup lang="ts">
import { RouterView, useRoute } from 'vue-router'
import { computed } from 'vue'
import { Monitor, TrendCharts } from '@element-plus/icons-vue'

const route = useRoute()
const activeMenu = computed(() => route.path)
</script>

<template>
  <div class="common-layout">
    <el-container>
      <el-aside width="200px">
        <el-menu
          :default-active="activeMenu"
          class="el-menu-vertical"
          router
        >
          <div class="logo">
            <h3>Signal Monitor</h3>
          </div>
          <el-menu-item index="/dkx">
            <el-icon><Monitor /></el-icon>
            <span>DKX 信号检测</span>
          </el-menu-item>
          <el-menu-item index="/ma">
            <el-icon><TrendCharts /></el-icon>
            <span>双均线策略</span>
          </el-menu-item>
        </el-menu>
      </el-aside>
      <el-container>
        <el-header>
          <div class="header-content">
            <h2>{{ route.meta.title || '仪表盘' }}</h2>
          </div>
        </el-header>
        <el-main>
          <RouterView />
        </el-main>
      </el-container>
    </el-container>
  </div>
</template>

<style scoped>
.common-layout {
  height: 100vh;
}
.el-container {
  height: 100%;
}
.el-aside {
  background-color: #f5f7fa;
  border-right: 1px solid #dcdfe6;
}
.logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #e6e8eb;
  color: #303133;
}
.el-header {
  background-color: #fff;
  border-bottom: 1px solid #dcdfe6;
  display: flex;
  align-items: center;
}
</style>
