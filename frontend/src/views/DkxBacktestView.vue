<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { nextTick } from 'vue'

interface Trade {
  id: number
  time: string
  symbol: string
  direction: string
  price: number
  quantity: number
  commission: number
  profit: number
  cumulative_profit: number
  position_dir: number
}

interface Statistics {
  total_trades: number
  win_rate: number
  max_drawdown: number
  sharpe_ratio: number
  total_return: number
  annualized_return: number
  total_profit: number
  final_equity: number
  realized_profit: number
  floating_profit: number
  avg_profit: number
  avg_win: number
  avg_loss: number
  profit_factor: number
  max_consecutive_wins: number
  max_consecutive_losses: number
  return_on_margin: number
  max_margin_used: number
  avg_slippage: number
  max_slippage: number
  strategy_capacity: number
  max_daily_loss: number
}

interface BacktestResult {
  symbol: string
  symbol_name: string
  trades: Trade[]
  chart_data: any[]
  statistics: Statistics
}

const form = reactive({
  symbols: [] as string[],
  market: 'futures',
  period: '60',
  dateRange: [] as string[],
  initialCapital: 100000,
  lotSize: 20
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

import { Delete, ArrowDown, ArrowUp, CaretRight, CaretBottom } from '@element-plus/icons-vue'

const loading = ref(false)
const symbolOptions = ref<{value: string, label: string}[]>([])
const symbolLoading = ref(false)
const results = ref<BacktestResult[]>([])
const currentSymbol = ref('')
const summaryTableRef = ref()

// Section Collapse State
const sectionState = reactive({
    multiSummary: true,
    singleSummary: true,
    chart: true,
    tradeList: true
})

const loadSectionState = () => {
    const saved = localStorage.getItem('dkxSectionState')
    if (saved) {
        try {
            const parsed = JSON.parse(saved)
            Object.assign(sectionState, parsed)
        } catch(e) { console.error(e) }
    }
}
loadSectionState()

const toggleSection = (key: keyof typeof sectionState) => {
    sectionState[key] = !sectionState[key]
    localStorage.setItem('dkxSectionState', JSON.stringify(sectionState))
}

// Hot Symbols Default (will be fetched from backend)
const defaultHotSymbols = ref(['RB0', 'I0', 'CU0', 'M0', 'TA0'])

// Initialize date range (last 1 year)
const end = new Date()
const start = new Date()
start.setFullYear(start.getFullYear() - 1)

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

const toggleAllExpansion = (expanded: boolean) => {
    results.value.forEach(row => {
        summaryTableRef.value?.toggleRowExpansion(row, expanded)
    })
}


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
    
    const newOptions = response.data
    const optionMap = new Map(symbolOptions.value.map(o => [o.value, o]))
    newOptions.forEach((o: any) => optionMap.set(o.value, o))
    symbolOptions.value = Array.from(optionMap.values())
    
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

const runBacktest = async () => {
  if (!form.symbols || form.symbols.length === 0) {
    ElMessage.warning('请选择标的')
    return
  }
  if (!form.dateRange || form.dateRange.length !== 2) {
    ElMessage.warning('请选择时间范围')
    return
  }

  loading.value = true
  results.value = []
  
  try {
    const response = await axios.post('/api/backtest/dkx', {
      symbols: form.symbols,
      market: form.market,
      period: form.period,
      start_time: form.dateRange[0],
      end_time: form.dateRange[1],
      initial_capital: form.initialCapital,
      lot_size: form.lotSize
    })
    
    results.value = response.data.results
    
    if (results.value.length > 0) {
      currentSymbol.value = results.value[0].symbol
      await nextTick()
      initChart(results.value[0])
    }
    
    ElMessage.success('回测完成')
  } catch (error) {
    ElMessage.error('回测失败: ' + error)
  } finally {
    loading.value = false
  }
}

const handleSymbolChange = (val: string) => {
  currentSymbol.value = val
  const res = results.value.find(r => r.symbol === val)
  if (res) {
    nextTick(() => initChart(res))
  }
}

const handleSortChange = ({ prop, order }: { prop: string, order: string }) => {
  if (!order) return
  
  results.value.sort((a, b) => {
    let valA, valB
    
    // Handle nested properties
    if (prop.includes('.')) {
      const parts = prop.split('.')
      // @ts-ignore
      valA = a[parts[0]][parts[1]]
      // @ts-ignore
      valB = b[parts[0]][parts[1]]
    } else {
      // @ts-ignore
      valA = a[prop]
      // @ts-ignore
      valB = b[prop]
    }
    
    // Handle numeric comparison
    if (typeof valA === 'number' && typeof valB === 'number') {
        if (order === 'ascending') {
            return valA - valB
        } else {
            return valB - valA
        }
    }
    
    // Handle string comparison
    if (valA === undefined || valA === null) valA = ''
    if (valB === undefined || valB === null) valB = ''
    
    if (order === 'ascending') {
      return valA > valB ? 1 : (valA < valB ? -1 : 0)
    } else {
      return valA < valB ? 1 : (valA > valB ? -1 : 0)
    }
  })
}

const initChart = (result: BacktestResult) => {
  const chartDom = document.getElementById('backtest-chart')
  if (!chartDom) return
  
  // Dispose existing instance if any to avoid conflicts
  const existingInstance = echarts.getInstanceByDom(chartDom)
  if (existingInstance) {
    existingInstance.dispose()
  }
  
  const myChart = echarts.init(chartDom)
  
  const data = result.chart_data
  const trades = result.trades
  
  const dates = data.map(item => item.date)
  const kLineData = data.map(item => [item.open, item.close, item.low, item.high])
  const dkxData = data.map(item => item.dkx)
  const madkxData = data.map(item => item.madkx)
  
  // Prepare Markers
  const markers: any[] = []
  const processedTimes = new Set()

  trades.forEach(trade => {
    if (processedTimes.has(trade.time)) return
    
    const sameTimeTrades = trades.filter(t => t.time === trade.time)
    
    let label = ''
    let color = ''
    let rotate = 0
    let offset = 0
    
    const hasCloseShort = sameTimeTrades.some(t => t.direction === '平空')
    const hasOpenLong = sameTimeTrades.some(t => t.direction === '开多')
    const hasCloseLong = sameTimeTrades.some(t => t.direction === '平多')
    const hasOpenShort = sameTimeTrades.some(t => t.direction === '开空')
    
    if (hasCloseShort && hasOpenLong) {
        label = '反多'
        color = '#ff4d4f'
        rotate = 0
        offset = 15
    } else if (hasCloseLong && hasOpenShort) {
        label = '反空'
        color = '#52c41a'
        rotate = 180
        offset = -15
    } else {
        // Regular single trade
        if (trade.direction === '开多' || trade.direction === '平空') {
             label = '买入'
             color = '#ff4d4f'
             rotate = 0
             offset = 15
        } else {
             label = '卖出'
             color = '#52c41a'
             rotate = 180
             offset = -15
        }
    }

    const tooltip = sameTimeTrades.map(t => 
        `操作: ${t.direction}<br/>价格: ${t.price}<br/>盈亏: ${t.profit.toFixed(2)}`
    ).join('<br/>----------------<br/>')

    markers.push({
      name: label,
      coord: [trade.time, trade.price],
      value: label,
      itemStyle: { color: color },
      symbol: 'arrow',
      symbolSize: 15,
      symbolRotate: rotate,
      label: { 
          show: true,
          formatter: label,
          offset: [0, offset],
          fontWeight: 'bold',
          color: color
      },
      tooltip: {
          formatter: `时间: ${trade.time}<br/>${tooltip}`
      }
    })
    
    processedTimes.add(trade.time)
  })
  
  const option = {
    title: { text: `回测图表 - ${result.symbol_name || ''} ${result.symbol}` },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' }
    },
    legend: { data: ['K线', 'DKX', 'MADKX'] },
    grid: { left: '3%', right: '3%', bottom: '30px', top: '40px', containLabel: true },
    xAxis: { type: 'category', data: dates, scale: true },
    yAxis: { scale: true, splitArea: { show: true } },
    dataZoom: [{ type: 'inside', start: 0, end: 100 }, { show: true, type: 'slider', top: '92%' }],
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        data: kLineData,
        markPoint: {
          data: markers,
          symbolSize: 30, // Arrow size increased
          label: {
              show: true,
              fontSize: 12,
              fontWeight: 'bold'
          }
        }
      },
      {
        name: 'DKX',
        type: 'line',
        data: dkxData,
        smooth: true,
        lineStyle: { width: 2, color: '#1890ff' } // Blue
      },
      {
        name: 'MADKX',
        type: 'line',
        data: madkxData,
        smooth: true,
        lineStyle: { width: 2, type: 'dashed', color: '#faad14' } // Gold/Orange
      }
    ]
  }
  
  myChart.setOption(option)
}

const currentStats = computed(() => {
  if (!currentSymbol.value) return null
  const res = results.value.find(r => r.symbol === currentSymbol.value)
  return res ? res.statistics : null
})

const currentTrades = computed(() => {
  if (!currentSymbol.value) return []
  const res = results.value.find(r => r.symbol === currentSymbol.value)
  return res ? res.trades : []
})

const exportExcel = () => {
  if (currentTrades.value.length === 0) return
  
  const csvContent = "data:text/csv;charset=utf-8," 
    + "ID,Time,Symbol,Direction,Price,Real Price,Slippage,Quantity,Commission,Profit,Cumulative Profit\n"
    + currentTrades.value.map((t: any) => 
        `${t.id},${t.time},${t.symbol},${t.direction},${t.price},${t.real_price || t.price},${t.slippage || 0},${t.quantity},${t.commission.toFixed(2)},${t.profit.toFixed(2)},${t.cumulative_profit.toFixed(2)}`
      ).join("\n")
    
  const encodedUri = encodeURI(csvContent)
  const link = document.createElement("a")
  const currentRes = results.value.find(r => r.symbol === currentSymbol.value)
  const name = currentRes ? currentRes.symbol_name : ''
  link.setAttribute("href", encodedUri)
  link.setAttribute("download", `backtest_${currentSymbol.value}_${name}.csv`)
  document.body.appendChild(link)
  link.click()
}

const exportPDF = () => {
    window.print()
}

searchSymbols('')
</script>

<template>
  <div class="dkx-backtest-view">
    <el-card class="box-card">
      <template #header>
        <div class="card-header">
          <span>DKX 信号策略回测</span>
        </div>
      </template>
      
      <!-- Filters -->
      <el-form :inline="true" :model="form" class="demo-form-inline">
        <el-form-item label="市场">
          <el-select v-model="form.market" placeholder="选择市场" style="width: 100px" @change="() => { form.symbols = []; searchSymbols('') }">
            <el-option label="股票" value="stock" />
            <el-option label="期货" value="futures" />
          </el-select>
        </el-form-item>
        
        <el-form-item label="标的代码">
           <div style="display: flex; gap: 5px; align-items: center;">
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
                 :label="item.label"
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
            <el-option label="日线" value="daily" />
            <el-option label="周线" value="weekly" />
            <el-option label="月线" value="monthly" />
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
        
        <el-form-item label="初始资金">
          <el-input-number v-model="form.initialCapital" :min="10000" :max="10000000" :step="10000" style="width: 140px" />
        </el-form-item>
        
        <el-form-item label="开仓手数">
          <el-input-number v-model="form.lotSize" :min="1" :max="1000" style="width: 100px" />
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
          <el-button type="primary" @click="runBacktest" :loading="loading">开始回测</el-button>
        </el-form-item>
      </el-form>
      
      <!-- Result Tabs if multiple symbols -->
      <div v-if="results.length > 0" style="margin-top: 20px;">
        
        <!-- Summary Table for Multiple Symbols -->
        <div v-if="results.length > 1" class="section-container">
          <div class="section-header" @click="toggleSection('multiSummary')">
              <div class="header-left">
                  <el-icon class="collapse-icon"><component :is="sectionState.multiSummary ? 'CaretBottom' : 'CaretRight'" /></el-icon>
                  <h3>多品种统计汇总</h3>
                  <span v-if="!sectionState.multiSummary" class="header-summary">
                      共 {{ results.length }} 个品种，平均胜率 {{ (results.reduce((a,b)=>a+b.statistics.win_rate,0)/results.length*100).toFixed(1) }}%
                  </span>
              </div>
              <div class="header-actions" @click.stop>
                  <el-button v-show="sectionState.multiSummary" size="small" @click="toggleAllExpansion(true)" :icon="ArrowDown">全部展开</el-button>
                  <el-button v-show="sectionState.multiSummary" size="small" @click="toggleAllExpansion(false)" :icon="ArrowUp">全部收起</el-button>
              </div>
          </div>
          <el-collapse-transition>
            <div v-show="sectionState.multiSummary">
                <el-table ref="summaryTableRef" :data="results" style="width: 100%" @sort-change="handleSortChange" border stripe>
            <el-table-column type="expand">
              <template #default="props">
                <el-descriptions :column="4" border size="small">
                     <el-descriptions-item label="总交易次数">{{ props.row.statistics.total_trades }}</el-descriptions-item>
                     <el-descriptions-item label="胜率">{{ (props.row.statistics.win_rate * 100).toFixed(2) }}%</el-descriptions-item>
                     <el-descriptions-item label="夏普比率">{{ props.row.statistics.sharpe_ratio.toFixed(2) }}</el-descriptions-item>
                     <el-descriptions-item label="最大回撤">{{ (props.row.statistics.max_drawdown * 100).toFixed(2) }}%</el-descriptions-item>
                     <el-descriptions-item label="平均盈利">{{ props.row.statistics.avg_win ? props.row.statistics.avg_win.toFixed(2) : '-' }}</el-descriptions-item>
                     <el-descriptions-item label="平均亏损">{{ props.row.statistics.avg_loss ? props.row.statistics.avg_loss.toFixed(2) : '-' }}</el-descriptions-item>
                     <el-descriptions-item label="最大连胜">{{ props.row.statistics.max_consecutive_wins }}</el-descriptions-item>
                     <el-descriptions-item label="最大连败">{{ props.row.statistics.max_consecutive_losses }}</el-descriptions-item>
                </el-descriptions>
              </template>
            </el-table-column>
            <el-table-column prop="symbol" label="品种代码" sortable="custom" width="110" />
            <el-table-column prop="symbol_name" label="品种名称" width="110" />
            <el-table-column prop="statistics.return_on_margin" label="收益率 (ROI)" sortable="custom" width="140">
              <template #default="scope">
                <span :style="{ color: scope.row.statistics.return_on_margin > 0 ? 'red' : (scope.row.statistics.return_on_margin < 0 ? 'green' : '') }">
                  {{ (scope.row.statistics.return_on_margin * 100).toFixed(2) }}%
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="statistics.profit_factor" label="盈亏比" sortable="custom" width="110">
              <template #default="scope">
                {{ scope.row.statistics.profit_factor !== null ? scope.row.statistics.profit_factor.toFixed(2) : '-' }}
              </template>
            </el-table-column>
            <el-table-column prop="statistics.total_profit" label="总盈亏" sortable="custom" width="120">
              <template #default="scope">
                 <span :style="{ color: scope.row.statistics.total_profit > 0 ? 'red' : (scope.row.statistics.total_profit < 0 ? 'green' : '') }">
                  {{ scope.row.statistics.total_profit.toFixed(0) }}
                 </span>
              </template>
            </el-table-column>
            <el-table-column prop="statistics.max_drawdown" label="最大回撤" sortable="custom" width="120">
              <template #default="scope">
                {{ (scope.row.statistics.max_drawdown * 100).toFixed(2) }}%
              </template>
            </el-table-column>
             <el-table-column prop="statistics.win_rate" label="胜率" sortable="custom" width="100">
              <template #default="scope">
                {{ (scope.row.statistics.win_rate * 100).toFixed(1) }}%
              </template>
            </el-table-column>
            <el-table-column label="操作" width="100" fixed="right">
              <template #default="scope">
                <el-button type="primary" link @click="currentSymbol = scope.row.symbol; handleSymbolChange(scope.row.symbol)">查看详情</el-button>
              </template>
            </el-table-column>
          </el-table>
            </div>
          </el-collapse-transition>
        </div>

        <el-radio-group v-model="currentSymbol" @change="handleSymbolChange" style="margin-bottom: 20px;">
          <el-radio-button v-for="res in results" :key="res.symbol" :label="res.symbol">{{ res.symbol_name || res.symbol }} ({{ res.symbol }})</el-radio-button>
        </el-radio-group>
        
        <!-- Statistics Panel -->
        <div v-if="currentStats" class="section-container">
            <div class="section-header" @click="toggleSection('singleSummary')">
                <div class="header-left">
                    <el-icon class="collapse-icon"><component :is="sectionState.singleSummary ? 'CaretBottom' : 'CaretRight'" /></el-icon>
                    <h3>统计汇总</h3>
                    <span v-if="!sectionState.singleSummary" class="header-summary">
                        总盈亏: {{ currentStats.total_profit.toFixed(2) }} | 胜率: {{ (currentStats.win_rate * 100).toFixed(2) }}% | 回撤: {{ (currentStats.max_drawdown * 100).toFixed(2) }}%
                    </span>
                </div>
            </div>
            <el-collapse-transition>
                <div v-show="sectionState.singleSummary">
                    <el-descriptions :column="4" border>
                      <el-descriptions-item label="总交易次数">{{ currentStats.total_trades }}</el-descriptions-item>
                      <el-descriptions-item label="胜率">{{ (currentStats.win_rate * 100).toFixed(2) }}%</el-descriptions-item>
                      <el-descriptions-item label="总盈亏 (权益)">{{ currentStats.total_profit.toFixed(2) }}</el-descriptions-item>
                      <el-descriptions-item label="平仓盈亏 (已结)">{{ currentStats.realized_profit ? currentStats.realized_profit.toFixed(2) : '-' }}</el-descriptions-item>
                      <el-descriptions-item label="浮动盈亏 (未结)">{{ currentStats.floating_profit ? currentStats.floating_profit.toFixed(2) : '-' }}</el-descriptions-item>
                      <el-descriptions-item label="最大回撤">{{ (currentStats.max_drawdown * 100).toFixed(2) }}%</el-descriptions-item>
                      <el-descriptions-item label="夏普比率">{{ currentStats.sharpe_ratio.toFixed(2) }}</el-descriptions-item>
                      <el-descriptions-item label="总收益率">{{ (currentStats.total_return * 100).toFixed(2) }}%</el-descriptions-item>
                      <el-descriptions-item label="期末权益">{{ currentStats.final_equity.toFixed(2) }}</el-descriptions-item>
                      <el-descriptions-item label="盈亏比">{{ currentStats.profit_factor ? currentStats.profit_factor.toFixed(2) : '-' }}</el-descriptions-item>
                      <el-descriptions-item label="平均盈利">{{ currentStats.avg_win ? currentStats.avg_win.toFixed(2) : '-' }}</el-descriptions-item>
                      <el-descriptions-item label="平均亏损">{{ currentStats.avg_loss ? currentStats.avg_loss.toFixed(2) : '-' }}</el-descriptions-item>
                      <el-descriptions-item label="最大连胜">{{ currentStats.max_consecutive_wins }}</el-descriptions-item>
                      <el-descriptions-item label="最大连败">{{ currentStats.max_consecutive_losses }}</el-descriptions-item>
                    </el-descriptions>
                </div>
            </el-collapse-transition>
        </div>
        
        <!-- Chart -->
        <div class="section-container" style="margin-top: 20px;">
            <div class="section-header" @click="toggleSection('chart')">
                <div class="header-left">
                    <el-icon class="collapse-icon"><component :is="sectionState.chart ? 'CaretBottom' : 'CaretRight'" /></el-icon>
                    <h3>回测图表区域</h3>
                    <span v-if="!sectionState.chart" class="header-summary">
                        {{ currentSymbol }} {{ form.period }}分钟 K线图
                    </span>
                </div>
            </div>
            <el-collapse-transition>
                <div v-show="sectionState.chart">
                    <div id="backtest-chart" style="width: 100%; height: 500px;"></div>
                </div>
            </el-collapse-transition>
        </div>
        
        <!-- Trade List -->
        <div class="section-container" style="margin-top: 20px;">
            <div class="section-header" @click="toggleSection('tradeList')">
                <div class="header-left">
                    <el-icon class="collapse-icon"><component :is="sectionState.tradeList ? 'CaretBottom' : 'CaretRight'" /></el-icon>
                    <h3>交易明细</h3>
                    <span v-if="!sectionState.tradeList" class="header-summary">
                        共 {{ currentTrades.length }} 笔交易
                    </span>
                </div>
                <div class="header-actions" @click.stop v-show="sectionState.tradeList">
                    <el-button type="primary" size="small" @click="exportExcel">导出CSV</el-button>
                    <el-button type="success" size="small" @click="exportPDF">打印报告 / 导出PDF</el-button>
                </div>
            </div>
            <el-collapse-transition>
                <div v-show="sectionState.tradeList">
                    <el-table :data="currentTrades" style="width: 100%" height="400" border stripe>
          <el-table-column prop="id" label="ID" width="60" />
          <el-table-column prop="time" label="时间" width="160" sortable />
          <el-table-column prop="symbol" label="合约" width="80" />
          <el-table-column prop="direction" label="方向" width="80">
            <template #default="scope">
              <el-tag :type="(scope.row.direction === '开多' || scope.row.direction === '平空') ? 'danger' : 'success'">
                {{ scope.row.direction }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="price" label="价格" width="100" />
          <el-table-column prop="real_price" label="实际成交" width="100">
             <template #default="scope">{{ scope.row.real_price ? scope.row.real_price.toFixed(2) : scope.row.price }}</template>
          </el-table-column>
          <el-table-column prop="slippage" label="滑点" width="80">
             <template #default="scope">{{ scope.row.slippage ? scope.row.slippage.toFixed(1) : '0' }}</template>
          </el-table-column>
          <el-table-column prop="quantity" label="数量(手)" width="100" />
          <el-table-column prop="funds_occupied" label="资金占用" width="100">
             <template #default="scope">{{ scope.row.funds_occupied ? scope.row.funds_occupied.toFixed(0) : '-' }}</template>
          </el-table-column>
          <el-table-column prop="risk_degree" label="风险度" width="80">
             <template #default="scope">{{ scope.row.risk_degree ? (scope.row.risk_degree * 100).toFixed(1) + '%' : '-' }}</template>
          </el-table-column>
          <el-table-column prop="commission" label="手续费" width="100">
             <template #default="scope">{{ scope.row.commission.toFixed(2) }}</template>
          </el-table-column>
          <el-table-column prop="profit" label="盈亏" sortable width="100">
            <template #default="scope">
              <span :style="{ color: scope.row.profit > 0 ? 'red' : (scope.row.profit < 0 ? 'green' : 'black') }">
                {{ scope.row.profit !== 0 ? scope.row.profit.toFixed(2) : '-' }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="cumulative_profit" label="累计盈亏" sortable width="120">
             <template #default="scope">
              <span :style="{ color: scope.row.cumulative_profit > 0 ? 'red' : 'green' }">
                {{ scope.row.cumulative_profit.toFixed(2) }}
              </span>
            </template>
          </el-table-column>
           <el-table-column prop="daily_balance" label="当日结存" width="120">
             <template #default="scope">{{ scope.row.daily_balance ? scope.row.daily_balance.toFixed(2) : '-' }}</template>
          </el-table-column>
          <el-table-column prop="order_type" label="报单方式" width="90" />
          <el-table-column prop="counterparty" label="对手方" width="90" />
        </el-table>
                </div>
            </el-collapse-transition>
        </div>
        
      </div>
      <el-empty v-else description="请配置参数并开始回测" />
      
    </el-card>
  </div>
</template>

<style scoped>
.dkx-backtest-view {
  padding: 20px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.section-container {
    border: 1px solid #ebeef5;
    border-radius: 4px;
    margin-bottom: 20px;
    background: white;
    overflow: hidden;
}
.section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px 15px;
    background-color: #f5f7fa;
    cursor: pointer;
    user-select: none;
    transition: background-color 0.3s;
}
.section-header:hover {
    background-color: #e6e8eb;
}
.header-left {
    display: flex;
    align-items: center;
    gap: 10px;
}
.header-left h3 {
    margin: 0;
    font-size: 16px;
    font-weight: bold;
    color: #303133;
}
.collapse-icon {
    font-size: 16px;
    color: #909399;
    transition: transform 0.3s;
}
.header-summary {
    color: #909399;
    font-size: 13px;
    margin-left: 15px;
}
</style>
