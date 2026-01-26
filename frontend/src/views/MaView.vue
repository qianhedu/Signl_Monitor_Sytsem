<script setup lang="ts">
import { ref, reactive } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { nextTick } from 'vue'
import ExcelJS from 'exceljs'

interface SignalResult {
  symbol: string
  name?: string
  date: string
  signal: string
  close: number
  ma_short: number
  ma_long: number
  details: any
}

const form = reactive({
  symbols: ['RB0','FU0','JM0','MA0'],
  market: 'futures',
  period: '60',
  lookback: 10,
  short_period: 20,
  long_period: 55
})

const loading = ref(false)
const symbolOptions = ref<{value: string, label: string}[]>([])
const symbolLoading = ref(false)
const results = ref<SignalResult[]>([])
const chartDialogVisible = ref(false)
const currentSymbol = ref('')
let chartInstance: echarts.ECharts | null = null

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
    
    // 合并选项并全选
    const newOptions = response.data
    // 更新选项以包含新增项，保证显示正确
    // 使用 Map 结构避免重复
    const optionMap = new Map(symbolOptions.value.map(o => [o.value, o]))
    newOptions.forEach((o: any) => optionMap.set(o.value, o))
    symbolOptions.value = Array.from(optionMap.values())
    
    // 将新增代码加入已选集合（去重）
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

// 监听市场变更以清空或刷新选项
// ...（为简洁起见此处省略，可以按需实现）

const detect = async () => {
  if (!form.symbols || form.symbols.length === 0) {
    ElMessage.warning('请选择标的')
    return
  }

  loading.value = true
  try {
    // form.symbols 已是数组
    const response = await axios.post('/api/detect/ma', {
      symbols: form.symbols,
      market: form.market,
      period: form.period,
      lookback: form.lookback,
      short_period: form.short_period,
      long_period: form.long_period
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
  initChart(row.details.chart_data, row)
}

const initChart = (data: any[], row: SignalResult) => {
  const chartDom = document.getElementById('ma-chart-container')
  if (!chartDom) return
  
  const myChart = echarts.init(chartDom)
  chartInstance = myChart
  
  const dates = data.map(item => item.date)
  const kLineData = data.map(item => [item.open, item.close, item.low, item.high])
  const maShortData = data.map(item => item.ma_short)
  const maLongData = data.map(item => item.ma_long)
  const idx = dates.indexOf(row.date)
  const priceAtSignal = idx >= 0 ? data[idx].close : null
  const isBuy = row.signal === 'BUY'
  
  const option = {
    title: { text: `双均线图表 - ${currentSymbol.value}` },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' }
    },
    legend: { data: ['K线', `MA${form.short_period}`, `MA${form.long_period}`] },
    grid: { left: '5%', right: '5%', bottom: '5%' },
    xAxis: { type: 'category', data: dates, scale: true },
    yAxis: { scale: true, splitArea: { show: true } },
    dataZoom: [{ type: 'inside', start: 50, end: 100 }, { show: true, type: 'slider', top: '90%' }],
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        data: kLineData,
        markPoint: idx >= 0 && priceAtSignal !== null ? {
          symbol: 'circle',
          symbolSize: 15,
          symbolOffset: [0, -20],
          itemStyle: { color: isBuy ? '#d14a61' : '#6abf47' },
          label: { formatter: isBuy ? '买入' : '卖出', color: isBuy ? '#d14a61' : '#6abf47', position: 'top' },
          data: [
            { coord: [row.date, priceAtSignal] }
          ]
        } : undefined
      },
      {
        name: `MA${form.short_period}`,
        type: 'line',
        data: maShortData,
        smooth: true,
        lineStyle: { opacity: 0.8 }
      },
      {
        name: `MA${form.long_period}`,
        type: 'line',
        data: maLongData,
        smooth: true,
        lineStyle: { opacity: 0.8 }
      }
    ]
  }
  
  myChart.setOption(option)
}

const downloadChart = () => {
  if (!chartInstance) return
  const url = chartInstance.getDataURL({ type: 'png', pixelRatio: 2, backgroundColor: '#fff' })
  const link = document.createElement('a')
  link.href = url
  link.download = `${currentSymbol.value}_ma.png`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

const generateRowChart = async (row: SignalResult) => {
  const container = document.createElement('div')
  container.style.position = 'fixed'
  container.style.left = '-9999px'
  container.style.top = '-9999px'
  container.style.width = '600px'
  container.style.height = '360px'
  document.body.appendChild(container)
  const chart = echarts.init(container)
  const data = row.details.chart_data
  const dates = data.map((item: any) => item.date)
  const kLineData = data.map((item: any) => [item.open, item.close, item.low, item.high])
  const maShortData = data.map((item: any) => item.ma_short)
  const maLongData = data.map((item: any) => item.ma_long)
  const idx = dates.indexOf(row.date)
  const priceAtSignal = idx >= 0 ? data[idx].close : null
  const isBuy = row.signal === 'BUY'
  chart.setOption({
    title: { text: `${row.name ? row.name + ' (' + row.symbol + ')' : row.symbol}` },
    legend: { data: ['K线', `MA${form.short_period}`, `MA${form.long_period}`] },
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    grid: { left: '5%', right: '5%', bottom: '5%' },
    xAxis: { type: 'category', data: dates, scale: true },
    yAxis: { scale: true, splitArea: { show: true } },
    series: [
      { name: 'K线', type: 'candlestick', data: kLineData,
        markPoint: idx >= 0 && priceAtSignal !== null ? {
          symbol: 'circle', 
          symbolSize: 15,
          symbolOffset: [0, -20], 
          itemStyle: { color: isBuy ? '#d14a61' : '#6abf47' },
          label: { formatter: isBuy ? '买入' : '卖出', color: isBuy ? '#d14a61' : '#6abf47', position: 'top' },
          data: [{ coord: [row.date, priceAtSignal] }]
        } : undefined },
      { name: `MA${form.short_period}`, type: 'line', data: maShortData, smooth: true },
      { name: `MA${form.long_period}`, type: 'line', data: maLongData, smooth: true, lineStyle: { opacity: 0.8 } }
    ]
  })
  chart.resize()
  await new Promise(r => setTimeout(r, 200))
  const url = chart.getDataURL({ type: 'png', pixelRatio: 2, backgroundColor: '#fff' })
  chart.dispose()
  document.body.removeChild(container)
  return url
}

const exportExcel = async () => {
  if (!results.value.length) return
  const wb = new ExcelJS.Workbook()
  const ws = wb.addWorksheet('双均线信号')
  ws.columns = [
    { header: '标的', key: 'target', width: 18 },
    { header: '信号日期', key: 'date', width: 18 },
    { header: '信号', key: 'signal', width: 10 },
    { header: '收盘价', key: 'close', width: 10 },
    { header: '短期均线', key: 'ma_short', width: 10 },
    { header: '长期均线', key: 'ma_long', width: 10 },
    { header: '图表', key: 'chart', width: 75 }
  ]
  for (let i = 0; i < results.value.length; i++) {
    const r = results.value[i]
    const dataRow = ws.addRow({
      target: r.name ? `${r.name} (${r.symbol})` : r.symbol,
      date: r.date,
      signal: r.signal === 'BUY' ? '买入' : '卖出',
      close: r.close,
      ma_short: r.ma_short,
      ma_long: r.ma_long
    })
    // 可选：图片单独行
    dataRow.height = 280
    const url = await generateRowChart(r)
    const base64 = url.split(',')[1]
    const imageId = wb.addImage({ base64, extension: 'png' })
    ws.addImage(imageId, { tl: { col: 6, row: dataRow.number - 1 }, ext: { width: 600, height: 360 } })
  }
  const buf = await wb.xlsx.writeBuffer()
  const blob = new Blob([buf], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = `MA指标信号.xlsx`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

// 初始化默认标的
searchSymbols('')
</script>

<template>
  <div class="ma-view">
    <el-card class="box-card">
      <template #header>
        <div class="card-header">
          <span>策略配置 (双均线)</span>
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
            <el-option label="5分钟" value="5" />
            <el-option label="15分钟" value="15" />
            <el-option label="30分钟" value="30" />
            <el-option label="60分钟" value="60" />
            <el-option label="120分钟" value="120" />
            <el-option label="240分钟" value="240" />
            <el-option label="日线" value="daily" />
            <el-option label="周线" value="weekly" />
            <el-option label="月线" value="monthly" />
          </el-select>
        </el-form-item>
        <el-form-item label="短期均线">
          <el-input-number v-model="form.short_period" :min="1" :max="100" style="width: 120px" />
        </el-form-item>
        <el-form-item label="长期均线">
          <el-input-number v-model="form.long_period" :min="1" :max="200" style="width: 120px" />
        </el-form-item>
        <el-form-item label="回溯K线数">
          <el-input-number v-model="form.lookback" :min="1" :max="20" style="width: 120px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="detect" :loading="loading">开始检测</el-button>
          <el-button type="success" @click="exportExcel" :disabled="results.length === 0">导出Excel</el-button>
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
        <el-table-column label="标的" width="200">
          <template #default="scope">
            {{ scope.row.name ? `${scope.row.name} (${scope.row.symbol})` : scope.row.symbol }}
          </template>
        </el-table-column>
        <el-table-column prop="date" label="信号日期" width="120" />
        <el-table-column prop="signal" label="信号" width="100">
          <template #default="scope">
            <el-tag :type="scope.row.signal === 'BUY' ? 'danger' : 'success'">
              {{ scope.row.signal === 'BUY' ? '买入' : '卖出' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="close" label="收盘价" />
        <el-table-column prop="ma_short" label="短期均线" />
        <el-table-column prop="ma_long" label="长期均线" />
        <el-table-column label="操作">
          <template #default="scope">
            <el-button size="small" @click="showChart(scope.row)">查看图表</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="chartDialogVisible" title="信号图表" width="80%" top="4vh">
      <div style="margin-bottom: 10px; text-align: right;">
        <el-button size="small" type="primary" @click="downloadChart">下载PNG</el-button>
      </div>
      <div id="ma-chart-container" style="width: 100%; height: 700px;"></div>
    </el-dialog>
  </div>
</template>

<style scoped>
.ma-view {
  padding: 20px;
}
</style>
