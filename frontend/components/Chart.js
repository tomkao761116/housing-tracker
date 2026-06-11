'use client';
import ReactECharts from 'echarts-for-react';

export default function Chart({ trendData, city }) {
  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      formatter: (params) => {
        const p = params[0];
        return `${p.name}<br/>均價: ${Number(p.value).toFixed(1)} 萬元/坪<br/>成交量: ${trendData.find(d => d.month === p.name)?.count || 0} 筆`;
      }
    },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: {
      type: 'category',
      data: trendData.map(d => d.month),
      axisLabel: { color: '#475569', fontSize: 12 }
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: '#475569', fontSize: 12, formatter: v => Number(v).toFixed(0) + ' 萬' },
      splitLine: { lineStyle: { color: '#e2e8f0' } }
    },
    series: [{
      name: '平均單價',
      type: 'line',
      smooth: true,
      data: trendData.map(d => d.avg_unit_price),
      itemStyle: { color: '#637d56' },
      areaStyle: {
        color: {
          type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(99,125,86,0.25)' },
            { offset: 1, color: 'rgba(99,125,86,0)' }
          ]
        }
      }
    }]
  };

  return <ReactECharts option={option} style={{ height: 350 }} />;
}
