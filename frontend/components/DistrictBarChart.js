'use client';
import ReactECharts from 'echarts-for-react';

export default function DistrictBarChart({ districtData }) {
  const sorted = [...districtData].sort((a, b) => b.avg_unit_price - a.avg_unit_price);
  
  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params) => {
        const p = params[0];
        const d = sorted[p.dataIndex];
        return `${d.district}<br/>均價: ${Number(d.avg_unit_price).toFixed(1)} 萬元/坪<br/>交易量: ${d.count} 筆`;
      }
    },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: {
      type: 'value',
      axisLabel: { color: '#475569', fontSize: 12 },
      splitLine: { lineStyle: { color: '#e2e8f0' } }
    },
    yAxis: {
      type: 'category',
      data: sorted.map(d => d.district),
      axisLabel: { color: '#475569', fontSize: 12 }
    },
    series: [{
      name: '平均單價',
      type: 'bar',
      data: sorted.map(d => d.avg_unit_price),
      itemStyle: {
        color: (params) => {
          const colors = ['#556b48','#637d56','#9ab57d','#4a5d3e','#3f4f34','#475569','#64748b','#94a3b8','#92400e','#b45309','#d97706','#b45309'];
          return colors[params.dataIndex % colors.length];
        },
        borderRadius: [0, 4, 4, 0]
      },
      label: {
        show: true,
        position: 'right',
        color: '#475569',
        fontSize: 12,
        formatter: (p) => Number(p.value).toFixed(1) + ' 萬'
      }
    }]
  };

  return <ReactECharts option={option} style={{ height: 450 }} />;
}
