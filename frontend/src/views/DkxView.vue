<script setup lang="ts">
import { ref, reactive } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { nextTick } from 'vue'
import ExcelJS from 'exceljs'

interface SignalResult {
  symbol: string
  symbol_name: string
  date: string
  signal: string
  close: number
  dkx: number
  madkx: number
  details: any
}

import { Delete } from '@element-plus/icons-vue'

  const form = reactive({
  symbols: ['600519', '000001'],
  market: 'futures',
  period: '60',
  lookback: 0,
  dateRange: [] as string[]
})

// Date shortcuts
const shortcuts = [
  {
    text: '近1个月',
    value: () => {
      const end = new Date()
      const start = new Date()
      start.setMonth(start.getMonth() - 1)
      return [start, end]
    },
  },
  {
    text: '近3个月',
    value: () => {
      const end = new Date()
      const start = new Date()
      start.setMonth(start.getMonth() - 3)
      return [start, end]
    },
  },
  {
    text: '近6个月',
    value: () => {
      const end = new Date()
      const start = new Date()
      start.setMonth(start.getMonth() - 6)
      return [start, end]
    },
  },
  {
    text: '近1年',
    value: () => {
      const end = new Date()
      const start = new Date()
      start.setFullYear(start.getFullYear() - 1)
      return [start, end]
    },
  },
]

const loading = ref(false)
const symbolOptions = ref<{value: string, label: string}[]>([])
const symbolLoading = ref(false)
const results = ref<SignalResult[]>([])
const chartDialogVisible = ref(false)
const currentSymbol = ref('')
const currentSymbolName = ref('')

const searchSymbols = async (query: string) => {
  symbolLoading.value = true
  try {
    const response = await axios.get('/api/symbols/search', {
      params: { q: query, market: form.market }
    })
    
    // Merge with existing selected options to ensure labels are preserved
    const newOptions = response.data
    const selectedMap = new Map()
    
    // Keep currently selected options
    if (form.symbols && form.symbols.length > 0) {
        symbolOptions.value.forEach(op => {
            if (form.symbols.includes(op.value)) {
                selectedMap.set(op.value, op)
            }
        })
    }
    
    // Add new options
    newOptions.forEach((op: any) => {
        selectedMap.set(op.value, op)
    })
    
    symbolOptions.value = Array.from(selectedMap.values())
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

// Hot Symbols Default (will be fetched from backend)
const defaultHotSymbols = ref(['RB0', 'I0', 'CU0', 'M0', 'TA0'])

// Initialize date range (last 1 year)
const end = new Date()
const start = new Date()
start.setFullYear(start.getFullYear() - 1)

// Format date to local string YYYY-MM-DD HH:mm:ss
const formatDate = (date: Date) => {
  const pad = (n: number) => n < 10 ? '0' + n : n
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

form.dateRange = [formatDate(start), formatDate(end)]

// Load Hot Symbols from LocalStorage or Default
const loadHotSymbols = async () => {
  // First try to fetch default from backend to ensure it's up to date
  try {
      const res = await axios.get('/api/symbols/hot')
      if (res.data && Array.isArray(res.data)) {
          defaultHotSymbols.value = res.data
      }
  } catch (e) {
      console.error('Failed to fetch hot symbols', e)
  }

  const saved = localStorage.getItem('userHotSymbols')
  if (saved) {
    try {
        const parsed = JSON.parse(saved)
        if (Array.isArray(parsed) && parsed.length > 0) {
            form.symbols = parsed
        }
    } catch (e) {
        console.error('Error parsing hot symbols', e)
        form.symbols = [...defaultHotSymbols.value]
    }
  } else {
    // First time entry or restore default
    form.symbols = [...defaultHotSymbols.value]
  }
  
  // Fetch symbol details for display
  if (form.symbols.length > 0) {
      try {
          const res = await axios.post('/api/symbols/info', {
              symbols: form.symbols,
              market: form.market
          })
          symbolOptions.value = res.data
      } catch (e) {
          console.error('Failed to fetch symbol info', e)
      }
  }
}

// Call on init
loadHotSymbols()

const saveHotSymbols = () => {
    if (form.symbols.length > 0) {
        localStorage.setItem('userHotSymbols', JSON.stringify(form.symbols))
        ElMessage.success('当前选择已保存为默认')
    }
}

const restoreDefaultHotSymbols = () => {
    form.symbols = [...defaultHotSymbols.value]
    localStorage.removeItem('userHotSymbols')
    ElMessage.success('已恢复默认热门品种')
}

const clearSymbols = () => {
    form.symbols = []
    results.value = []
    currentSymbol.value = ''
    ElMessage.info('已清空标的代码')
}

const detect = async () => {
  if (!form.symbols || form.symbols.length === 0) {
    ElMessage.warning('请选择标的')
    return
  }
  if (!form.dateRange || form.dateRange.length !== 2) {
    ElMessage.warning('请选择时间范围')
    return
  }

  loading.value = true
  try {
    const response = await axios.post('/api/detect/dkx', {
      symbols: form.symbols,
      market: form.market,
      period: form.period,
      lookback: form.lookback,
      start_time: form.dateRange && form.dateRange.length === 2 ? form.dateRange[0] : null,
      end_time: form.dateRange && form.dateRange.length === 2 ? form.dateRange[1] : null
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
  currentSymbolName.value = row.symbol_name
  chartDialogVisible.value = true
  
  await nextTick()
  initChart(row.details.chart_data, row.details.chart_signals || [])
}

const initChart = (data: any[], signals: any[]) => {
  const chartDom = document.getElementById('chart-container')
  if (!chartDom) return
  
  const myChart = echarts.init(chartDom)
  
  const dates = data.map(item => item.date)
  const kLineData = data.map(item => [item.open, item.close, item.low, item.high])
  const dkxData = data.map(item => item.dkx)
  const madkxData = data.map(item => item.madkx)

  const markPoints = signals.map(sig => ({
    name: `${sig.signal === 'BUY' ? 'DKX金叉' : 'DKX死叉'} @ ${sig.date}`,
    value: sig.signal === 'BUY' ? '买' : '卖',
    coord: [sig.date, sig.price],
    symbol: 'pin',
    symbolSize: 50,
    itemStyle: {
      color: sig.signal === 'BUY' ? '#ef5350' : '#26a69a'
    }
  }))

  const option = {
    title: { text: `${currentSymbolName.value} (${currentSymbol.value}) - DKX` },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' }
    },
    legend: { data: ['K线', 'DKX', 'MADKX'] },
    grid: { left: '3%', right: '3%', bottom: '30px', top: '40px', containLabel: true },
    xAxis: { type: 'category', data: dates, scale: true },
    yAxis: { scale: true, splitArea: { show: true } },
    dataZoom: [{ type: 'inside', start: 80, end: 100 }, { show: true, type: 'slider', top: '92%' }],
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        data: kLineData,
        markPoint: {
          data: markPoints,
          symbolSize: 50, // Increased size
          label: {
              fontSize: 14,
              fontWeight: 'bold'
          }
        }
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

const exportLoading = ref(false)

const generateChartImage = async (symbol: string, symbolName: string, data: any[], signals: any[]) => {
  const chartDom = document.getElementById('export-chart-container')
  if (!chartDom) return null
  
  let myChart = echarts.getInstanceByDom(chartDom)
  if (myChart) {
      myChart.dispose()
  }
  myChart = echarts.init(chartDom)
  
  const dates = data.map(item => item.date)
  const kLineData = data.map(item => [item.open, item.close, item.low, item.high])
  const dkxData = data.map(item => item.dkx)
  const madkxData = data.map(item => item.madkx)

  const markPoints = signals.map(sig => ({
    name: `${sig.signal === 'BUY' ? '金叉' : '死叉'}`,
    value: sig.signal === 'BUY' ? '买' : '卖',
    coord: [sig.date, sig.price],
    symbol: 'pin',
    symbolSize: 20,
    itemStyle: {
      color: sig.signal === 'BUY' ? '#ef5350' : '#26a69a'
    },
    label: { show: false }
  }))

  const option = {
    animation: false,
    title: { 
        text: `${symbolName} (${symbol})`,
        left: 'center',
        textStyle: { fontSize: 10 }
    },
    grid: { left: 5, right: 5, bottom: 5, top: 25 },
    xAxis: { type: 'category', data: dates, show: false },
    yAxis: { scale: true, splitLine: { show: false }, show: false },
    series: [
      {
        type: 'candlestick',
        data: kLineData,
        itemStyle: {
            color: '#ef5350',
            color0: '#26a69a',
            borderColor: '#ef5350',
            borderColor0: '#26a69a'
        },
        markPoint: {
          data: markPoints,
          symbolSize: 20
        }
      },
      {
        type: 'line',
        data: dkxData,
        showSymbol: false,
        lineStyle: { width: 1, color: '#FFB800' }
      },
      {
        type: 'line',
        data: madkxData,
        showSymbol: false,
        lineStyle: { width: 1, type: 'dashed', color: '#0099FF' }
      }
    ]
  }
  
  myChart.setOption(option)
  
  // Minimal wait for render
  await new Promise(resolve => setTimeout(resolve, 50))
  
  const base64 = myChart.getDataURL({
      type: 'png',
      pixelRatio: 1,
      backgroundColor: '#fff'
  })
  
  return base64
}

const exportData = async () => {
  if (results.value.length === 0) return
  
  exportLoading.value = true
  ElMessage.info('正在生成 Excel，请稍候...（包含图表生成，可能需要一些时间）')
  
  try {
      const workbook = new ExcelJS.Workbook()
      const worksheet = workbook.addWorksheet('DKX信号')
      
      // Define columns
      worksheet.columns = [
          { header: '标的', key: 'symbol', width: 18 },
          { header: '信号日期', key: 'date', width: 20 },
          { header: '信号', key: 'signal', width: 10 },
          { header: '收盘价', key: 'close', width: 12 },
          { header: 'DKX', key: 'dkx', width: 12 },
          { header: 'MADKX', key: 'madkx', width: 12 }
      ]
      
      // Style headers
      const headerRow = worksheet.getRow(1)
      headerRow.font = { bold: true, size: 12, color: { argb: 'FFFFFFFF' } }
      headerRow.fill = {
          type: 'pattern',
          pattern: 'solid',
          fgColor: { argb: 'FF409EFF' }
      }
      headerRow.alignment = { vertical: 'middle', horizontal: 'center' }
      
      // Process data row by row
      for (let i = 0; i < results.value.length; i++) {
          const r = results.value[i]
          const rowIdx = i + 2
          
          const row = worksheet.addRow({
              symbol: `${r.symbol_name} (${r.symbol})`,
              date: r.date,
              signal: r.signal === 'BUY' ? '买入' : '卖出',
              close: r.close ? Number(r.close).toFixed(2) : '-',
              dkx: r.dkx ? Number(r.dkx).toFixed(2) : '-',
              madkx: r.madkx ? Number(r.madkx).toFixed(2) : '-',
              chart: ''
          })
          
          // Style cells
          row.alignment = { vertical: 'middle', horizontal: 'center' }
          
          // Color for Signal
          const signalCell = row.getCell('signal')
          if (r.signal === 'BUY') {
              signalCell.font = { color: { argb: 'FFF56C6C' }, bold: true }
          } else {
              signalCell.font = { color: { argb: 'FF67C23A' }, bold: true }
          }
          
          // Generate and add chart image
          if (r.details && r.details.chart_data) {
              const base64 = await generateChartImage(r.symbol, r.symbol_name, r.details.chart_data, r.details.chart_signals || [])
              if (base64) {
                  const imageId = workbook.addImage({
                      base64: base64,
                      extension: 'png',
                  })
                  
                  // Add image to the last column (L, index 11)
                  worksheet.addImage(imageId, {
                      tl: { col: 6, row: rowIdx - 1 },
                      ext: { width: 300, height: 100 },
                      editAs: 'oneCell'
                  })
                  
                  // Adjust row height to fit image
                  row.height = 80
              }
          }
      }
      
      // Export
      const buffer = await workbook.xlsx.writeBuffer()
      const blob = new Blob([buffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `dkx_signals_${new Date().getTime()}.xlsx`
      link.click()
      URL.revokeObjectURL(url)
      
      ElMessage.success('导出成功！')
      
  } catch (e) {
      console.error(e)
      ElMessage.error('导出失败')
  } finally {
      exportLoading.value = false
  }
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
               style="width: 200px"
               collapse-tags
               collapse-tags-tooltip
             >
               <el-option
                  v-for="item in symbolOptions"
                  :key="item.value"
                  :label="item.label.startsWith(item.value) ? item.label : (item.value + ' ' + item.label)"
                  :value="item.value"
                />
             </el-select>
             <el-button type="danger" :icon="Delete" circle @click="clearSymbols" title="清空" size="small"></el-button>
             <el-dropdown split-button type="primary" size="small" @click="saveHotSymbols" title="保存当前为热门">
                保存
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item @click="restoreDefaultHotSymbols">恢复默认</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
             </el-dropdown>
             <el-button v-if="form.market === 'stock'" size="small" @click="addBatch('hs300')">沪深300</el-button>
             <el-button v-if="form.market === 'futures'" size="small" @click="addBatch('all_futures')">所有期货</el-button>
           </div>
        </el-form-item>
        <el-form-item label="周期">
          <el-select v-model="form.period" placeholder="选择周期" style="width: 100px">
            <el-option label="周线" value="weekly" />
            <el-option label="日线" value="daily" />
            <el-option label="240分钟" value="240" />
            <el-option label="180分钟" value="180" />
            <el-option label="120分钟" value="120" />
            <el-option label="90分钟" value="90" />
            <el-option label="60分钟" value="60" />
            <el-option label="30分钟" value="30" />
            <el-option label="15分钟" value="15" />
            <el-option label="5分钟" value="5" />
          </el-select>
        </el-form-item>
        <el-form-item label="回溯K线数">
          <el-input-number v-model="form.lookback" :min="0" :max="200" style="width: 120px" />
        </el-form-item>
        <el-form-item label="时间范围">
          <el-date-picker
            v-model="form.dateRange"
            type="datetimerange"
            :shortcuts="shortcuts"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            value-format="YYYY-MM-DD HH:mm:ss"
            style="width: 350px"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="detect" :loading="loading">开始检测</el-button>
          <el-button type="success" @click="exportData" :loading="exportLoading" :disabled="results.length === 0">导出Excel</el-button>
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
        <el-table-column label="标的" min-width="100">
          <template #default="scope">
            <div style="text-align: left">
                {{ scope.row.symbol_name }} ({{ scope.row.symbol }})
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="date" label="信号日期"/>
        <el-table-column prop="signal" label="信号">
          <template #default="scope">
            <el-tag :type="scope.row.signal === 'BUY' ? 'danger' : 'success'">
              {{ scope.row.signal === 'BUY' ? '买入' : '卖出' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="close" label="收盘价">
            <template #default="scope">{{ scope.row.close ? Number(scope.row.close).toFixed(2) : '-' }}</template>
        </el-table-column>
        <el-table-column prop="dkx" label="DKX">
            <template #default="scope">{{ scope.row.dkx ? Number(scope.row.dkx).toFixed(2) : '-' }}</template>
        </el-table-column>
        <el-table-column prop="madkx" label="MADKX">
            <template #default="scope">{{ scope.row.madkx ? Number(scope.row.madkx).toFixed(2) : '-' }}</template>
        </el-table-column>
        <el-table-column label="操作">
          <template #default="scope">
            <el-button size="small" @click="showChart(scope.row)">查看图表</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="chartDialogVisible" title="信号图表" width="90%">
      <div id="chart-container" style="width: 100%; height: 800px;"></div>
    </el-dialog>

    <!-- Hidden container for export chart generation -->
    <div id="export-chart-container" style="width: 600px; height: 300px; position: absolute; left: -9999px; visibility: hidden;"></div>
  </div>
</template>

<style scoped>
.dkx-view {
  padding: 20px;
}
</style>
