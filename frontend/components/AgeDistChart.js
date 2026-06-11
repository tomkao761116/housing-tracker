'use client';
import ReactECharts from 'echarts-for-react';

export default function AgeDistChart({ data }) {
  const colors = ['#637d56', '#475569', '#92400e', '#dc2626', '#6b7280'];

  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params) => {
        const p = params[0];
        return `${p.name}<br/>${p.marker} ${p.seriesName}: ${p.value} 筆`;
      }
    },
    legend: {
      top: 0,
      textStyle: { color: '#475569', fontSize: 11 }
    },
    grid: {
      left: 30, right: 15, top: 35, bottom: 30, containLabel: true
    },
    xAxis: {
      type: 'category',
      data: data.map(d => d.label),
      axisLabel: { color: '#64748b', fontSize: 11 },
      axisLine: { lineStyle: { color: '#cbd5e1' } }
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: '#64748b', fontSize: 11, formatter: '{value} 筆' },
      splitLine: { lineStyle: { color: '#e2e8f0' } }
    },
    series: [{
      name: '交易筆數',
      type: 'bar',
      barWidth: '50%',
      data: data.map((d, i) => ({
        value: d.count,
        itemStyle: {
          color: ['#637d56', '#475569', '#92400e', '#dc2626', '#6b7280'][i % 5],
          borderRadius: [4, 4, 0, 0]
        }
      }))
    }]
  };

  if (!data.length) {
    return <div className="flex items-center justify-center h-[300px] text-stone-400">暫無資料</div>;
  }

  return <ReactECharts option={option} style={{ height: 320 }} />;
}
