'use client';
import ReactECharts from 'echarts-for-react';

export default function BuildingTypeChart({ data }) {
  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c} 筆 ({d}%)'
    },
    legend: {
      orient: 'vertical',
      right: '5%',
      top: 'center',
      textStyle: { color: '#475569', fontSize: 12 }
    },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['35%', '50%'],
      avoidLabelOverlap: true,
      itemStyle: { borderRadius: 6, borderColor: '#ffffff', borderWidth: 2 },
      label: { show: true, color: '#475569', fontSize: 12, formatter: '{b}\n{d}%' },
      labelLine: { lineStyle: { color: '#94a3b8' } },
      data: data.map((d, i) => ({
        name: d.type,
        value: d.count,
        itemStyle: {
          color: ['#475569','#637d56','#9ab57d','#92400e','#4a5d3e','#94a3b8','#3f4f34','#b45309'][i % 8]
        }
      }))
    }]
  };

  return <ReactECharts option={option} style={{ height: 350 }} />;
}
