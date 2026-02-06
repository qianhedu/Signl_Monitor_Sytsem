<script setup lang="ts">
import { RouterView, useRoute } from 'vue-router'
import { computed, ref, onMounted } from 'vue'
import { Monitor, TrendCharts, DataAnalysis, Expand, Fold } from '@element-plus/icons-vue'

const route = useRoute()
const activeMenu = computed(() => route.path)
const isCollapse = ref(false)

const toggleCollapse = () => {
  isCollapse.value = !isCollapse.value
  localStorage.setItem('menuCollapse', isCollapse.value.toString())
}

onMounted(() => {
  const savedState = localStorage.getItem('menuCollapse')
  if (savedState !== null) {
    isCollapse.value = savedState === 'true'
  }
})
</script>

<template>
  <div class="common-layout">
    <el-container>
      <el-aside :width="isCollapse ? '60px' : '240px'" class="aside-menu">
        <div class="logo-container">
          <div class="logo" v-show="!isCollapse">
            <h3>Signal Monitor</h3>
          </div>
          <div class="collapse-btn" @click="toggleCollapse">
            <el-icon :size="20">
              <Expand v-if="isCollapse" />
              <Fold v-else />
            </el-icon>
          </div>
        </div>
        <el-menu
          :default-active="activeMenu"
          class="el-menu-vertical"
          :collapse="isCollapse"
          :collapse-transition="false"
          router
        >
          <el-menu-item index="/dkx">
            <el-icon><Monitor /></el-icon>
            <template #title>DKX 信号检测</template>
          </el-menu-item>
          <el-menu-item index="/dkx-backtest">
            <el-icon><DataAnalysis /></el-icon>
            <template #title>DKX 信号策略统计</template>
          </el-menu-item>
          <el-menu-item index="/ma">
            <el-icon><TrendCharts /></el-icon>
            <template #title>双均线策略</template>
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
  transition: width 0.3s;
  overflow-x: hidden;
}
.logo-container {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #e6e8eb;
  color: #303133;
  position: relative;
}
.logo {
  white-space: nowrap;
  overflow: hidden;
}
.collapse-btn {
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  position: absolute;
  right: 10px;
}
/* When collapsed, center the button */
.el-aside[width="60px"] .collapse-btn {
  right: 0;
  width: 100%;
}
.el-menu-vertical {
  border-right: none;
}
.el-header {
  background-color: #fff;
  border-bottom: 1px solid #dcdfe6;
  display: flex;
  align-items: center;
}
</style>
