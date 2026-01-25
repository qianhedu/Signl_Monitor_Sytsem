<script setup lang="ts">
import { ref, reactive } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { nextTick } from 'vue'

interface SignalResult {
  symbol: string
  date: string
  signal: string
  close: number
  dkx: number
  madkx: number
  details: any
}

const form = reactive({
  symbols: ['600519', '000001'],
  market: 'stock',
  period: 'daily',
  lookback: 5
})

const loading = ref(false)
const symbolOptions = ref<{value: string, label: string}[]>([])
const symbolLoading = ref(false)
const results = ref<SignalResult[]>([])
const chartDialogVisible = ref(false)
const currentSymbol = ref('')

const searchSymbols = async (query: string) => {
  symbolLoading.value = true
  try {
    const response = await axios.get('/api/symbols/search', {
      params: { q: query, market: form.market }
    })
    symbolOptions.value = response.data
  } catch (e) {
    console.error(e)
  } finally {
    symbolLoading.value = false
  }
}

const addBatch = async (type: 'hs300' | 'all_futures') => {
  symbolLoading.value = true
  try {
    let query = ''
    if (type === 'hs300') query = 'hs300'
    if (type === 'all_futures') query = 'all'
    
    const response = await axios.get('/api/symbols/search', {
      params: { q: query, market: form.market }
    })
    
    // Merge options and select all
    const newOptions = response.data
    // Update options to include new ones so they display correctly
    // Use a map to avoid duplicates
    const optionMap = new Map(symbolOptions.value.map(o => [o.value, o]))
    newOptions.forEach((o: any) => optionMap.set(o.value, o))
    symbolOptions.value = Array.from(optionMap.values())
    
    // Add to selected symbols if not present
    const newValues = newOptions.map((o: any) => o.value)
    const currentSet = new Set(form.symbols)
    newValues.forEach((v: string) => currentSet.add(v))
    form.symbols = Array.from(currentSet)
    
    ElMessage.success(`已添加 ${newOptions.length} 个标的`)
  } catch (e) {
    ElMessage.error('批量添加失败')
    console.error(e)
  } finally {
    symbolLoading.value = false
  }
}

const detect = async () => {
  if (!form.symbols || form.symbols.length === 0) {
    ElMessage.warning('请选择标的')
    return
  }

  loading.value = true
  try {
    const response = await axios.post('/api/detect/dkx', {
      symbols: form.symbols,
      market: form.market,
      period: form.period,
      lookback: form.lookback
    })
    results.value = response.data.results
    if (results.value.length === 0) {
      ElMessage.info('指定范围内未检测到信号。')
    } else {
      ElMessage.success(`检测到 ${results.value.length} 个信号`)
    }
  } catch (error) {
    ElMessage.error('检测失败: ' + error)
  } finally {
    loading.value = false
  }
}

const showChart = async (row: SignalResult) => {
  currentSymbol.value = row.symbol
  chartDialogVisible.value = true
  
  await nextTick()
  initChart(row.details.chart_data)
}

const initChart = (data: any[]) => {
  const chartDom = document.getElementById('chart-container')
  if (!chartDom) return
  
  const myChart = echarts.init(chartDom)
  
  const dates = data.map(item => item.date)
  const kLineData = data.map(item => [item.open, item.close, item.low, item.high])
  const dkxData = data.map(item => item.dkx)
  const madkxData = data.map(item => item.madkx)
  
  const option = {
    title: { text: `DKX 图表 - ${currentSymbol.value}` },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' }
    },
    legend: { data: ['K线', 'DKX', 'MADKX'] },
    grid: { left: '10%', right: '10%', bottom: '15%' },
    xAxis: { type: 'category', data: dates, scale: true },
    yAxis: { scale: true, splitArea: { show: true } },
    dataZoom: [{ type: 'inside', start: 50, end: 100 }, { show: true, type: 'slider', top: '90%' }],
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        data: kLineData
      },
      {
        name: 'DKX',
        type: 'line',
        data: dkxData,
        smooth: true,
        lineStyle: { width: 2 }
      },
      {
        name: 'MADKX',
        type: 'line',
        data: madkxData,
        smooth: true,
        lineStyle: { width: 2, type: 'dashed' }
      }
    ]
  }
  
  myChart.setOption(option)
}

const exportData = () => {
  const csvContent = "data:text/csv;charset=utf-8," 
    + "Symbol,Date,Signal,Price,DKX,MADKX\n"
    + results.value.map(r => `${r.symbol},${r.date},${r.signal},${r.close},${r.dkx},${r.madkx}`).join("\n")
    
  const encodedUri = encodeURI(csvContent)
  const link = document.createElement("a")
  link.setAttribute("href", encodedUri)
  link.setAttribute("download", "dkx_signals.csv")
  document.body.appendChild(link)
  link.click()
}

searchSymbols('')
</script>

<template>
  <div class="dkx-view">
    <el-card class="box-card">
      <template #header>
        <div class="card-header">
          <span>策略配置 (DKX)</span>
        </div>
      </template>
      <el-form :inline="true" :model="form" class="demo-form-inline">
        <el-form-item label="市场">
          <el-select v-model="form.market" placeholder="选择市场" style="width: 120px" @change="() => { form.symbols = []; searchSymbols('') }">
            <el-option label="股票" value="stock" />
            <el-option label="期货" value="futures" />
          </el-select>
        </el-form-item>
        <el-form-item label="标的代码">
           <div style="display: flex; gap: 10px; align-items: center;">
             <el-select
               v-model="form.symbols"
               multiple
               filterable
               remote
               reserve-keyword
               placeholder="输入代码搜索"
               :remote-method="searchSymbols"
               :loading="symbolLoading"
               style="width: 300px"
               collapse-tags
               collapse-tags-tooltip
             >
               <el-option
                 v-for="item in symbolOptions"
                 :key="item.value"
                 :label="item.label"
                 :value="item.value"
               />
             </el-select>
             <el-button v-if="form.market === 'stock'" size="small" @click="addBatch('hs300')">添加沪深300</el-button>
             <el-button v-if="form.market === 'futures'" size="small" @click="addBatch('all_futures')">添加所有期货</el-button>
           </div>
        </el-form-item>
        <el-form-item label="周期">
          <el-select v-model="form.period" placeholder="选择周期" style="width: 120px">
            <el-option label="日线" value="daily" />
            <el-option label="周线" value="weekly" />
            <el-option label="月线" value="monthly" />
            <el-option label="60分钟" value="60" />
            <el-option label="30分钟" value="30" />
            <el-option label="15分钟" value="15" />
            <el-option label="5分钟" value="5" />
          </el-select>
        </el-form-item>
        <el-form-item label="回溯K线数">
          <el-input-number v-model="form.lookback" :min="1" :max="20" style="width: 120px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="detect" :loading="loading">开始检测</el-button>
          <el-button type="success" @click="exportData" :disabled="results.length === 0">导出</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="box-card" style="margin-top: 20px">
      <template #header>
        <div class="card-header">
          <span>检测结果</span>
        </div>
      </template>
      <el-table :data="results" style="width: 100%" v-loading="loading">
        <el-table-column prop="symbol" label="标的" width="120" />
        <el-table-column prop="date" label="信号日期" width="120" />
        <el-table-column prop="signal" label="信号" width="100">
          <template #default="scope">
            <el-tag :type="scope.row.signal === 'BUY' ? 'danger' : 'success'">
              {{ scope.row.signal === 'BUY' ? '买入' : '卖出' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="close" label="收盘价" />
        <el-table-column prop="dkx" label="DKX" />
        <el-table-column prop="madkx" label="MADKX" />
        <el-table-column label="操作">
          <template #default="scope">
            <el-button size="small" @click="showChart(scope.row)">查看图表</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="chartDialogVisible" title="信号图表" width="80%">
      <div id="chart-container" style="width: 100%; height: 400px;"></div>
    </el-dialog>
  </div>
</template>

<style scoped>
.dkx-view {
  padding: 20px;
}
</style>
