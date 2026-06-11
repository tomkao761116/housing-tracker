'use client';
import ReactECharts from 'echarts-for-react';

export default function PriceDistChart({ data }) {
  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params) => `${params[0].name}<br/>${params[0].value} 筆 (${params[1]?.value || 0}%)`
    },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: {
      type: 'category',
      data: data.map(d => d.label),
      axisLabel: { color: '#475569', fontSize: 12, rotate: 30 }
    },
    yAxis: [
      { type: 'value', name: '筆數', axisLabel: { color: '#475569', fontSize: 12 }, splitLine: { lineStyle: { color: '#e2e8f0' } } },
      { type: 'value', name: '%', axisLabel: { color: '#475569', fontSize: 12, formatter: '{value}%' }, splitLine: { show: false } }
    ],
    series: [
      {
        name: '筆數',
        type: 'bar',
        data: data.map(d => d.count),
        itemStyle: { color: '#637d56', borderRadius: [4, 4, 0, 0] }
      },
      {
        name: '百分比',
        type: 'line',
        yAxisIndex: 1,
        data: data.map(d => d.percentage),
        itemStyle: { color: '#92400e' },
        smooth: true
      }
    ]
  };

  return <ReactECharts option={option} style={{ height: 350 }} />;
}
