import React, { useEffect, useMemo, useRef, useState } from 'react';
import ReactECharts from 'echarts-for-react';
import { Button, Empty, Popover, Table, Tag } from 'antd';

const columns = [
  { title: '天数 / d', dataIndex: 'day', width: 76, fixed: 'left' },
  { title: '负压 / kPa', dataIndex: 'negativePressureKPa', width: 105 },
  { title: '钻孔绝压 / MPa', dataIndex: 'boreholePressureMPa', width: 128 },
  { title: '裂隙总压 / MPa', dataIndex: 'fracturePressureMPa', width: 128 },
  { title: '基质甲烷压 / MPa', dataIndex: 'matrixMethanePressureMPa', width: 145 },
  { title: '甲烷分压 / MPa', dataIndex: 'methanePartialPressureMPa', width: 125 },
  { title: '甲烷浓度 / %', dataIndex: 'methaneConcentrationPct', width: 118 },
  { title: '流量 / m³·d⁻¹', dataIndex: 'flowM3PerDay', width: 125 },
];

export default function SimulationResultPanel({ simulation }) {
  const values = simulation?.values || [];
  const tableRef = useRef(null);
  const [tableHeight, setTableHeight] = useState(120);
  useEffect(() => {
    if (!tableRef.current) return undefined;
    const observer = new ResizeObserver(([entry]) => setTableHeight(Math.max(40, entry.contentRect.height - 48)));
    observer.observe(tableRef.current);
    return () => observer.disconnect();
  }, [simulation]);

  const option = useMemo(() => ({
    backgroundColor: 'transparent',
    animation: false,
    tooltip: { trigger: 'axis' },
    legend: {
      type: 'scroll',
      top: 2,
      textStyle: { color: '#c9d6e2', fontSize: 10 },
      data: ['裂隙压力/MPa', '甲烷浓度/%', '流量/m³·d⁻¹'],
    },
    grid: { left: 44, right: 42, top: 50, bottom: 28 },
    xAxis: {
      type: 'category',
      data: values.map((v) => v.day),
      axisLabel: { color: '#8fa6bb', interval: values.length > 60 ? 9 : 'auto' },
      axisLine: { lineStyle: { color: '#365167' } },
    },
    yAxis: [
      {
        type: 'value', name: '压力/MPa', axisLabel: { color: '#8fa6bb' },
        nameTextStyle: { color: '#8fa6bb' }, splitLine: { lineStyle: { color: '#173044' } },
      },
      {
        type: 'value', name: '% / m³·d⁻¹', axisLabel: { color: '#8fa6bb' },
        nameTextStyle: { color: '#8fa6bb' }, splitLine: { show: false },
      },
    ],
    series: [
      {
        name: '裂隙压力/MPa', type: 'line', showSymbol: false, smooth: true,
        data: values.map((v) => v.fracturePressureMPa), lineStyle: { width: 2 },
      },
      {
        name: '甲烷浓度/%', type: 'line', yAxisIndex: 1, showSymbol: false, smooth: true,
        data: values.map((v) => v.methaneConcentrationPct), lineStyle: { width: 2 },
      },
      {
        name: '流量/m³·d⁻¹', type: 'line', yAxisIndex: 1, showSymbol: false, smooth: true,
        data: values.map((v) => v.flowM3PerDay), lineStyle: { width: 2 },
      },
    ],
  }), [values]);

  if (!simulation) {
    return <Empty description={<span style={{ color: '#7892a8' }}>设置参数后运行仿真，结果将在此显示</span>} />;
  }

  return (
    <div className="result-panel-content">
      <div className="result-meta">
        <Tag color="geekblue">降阶模型</Tag>
        <Tag color={simulation.dbSaved ? 'green' : 'default'}>
          {simulation.dbSaved ? '结果已保存' : '未启用数据库写入'}
        </Tag>
        <Popover title={simulation.engine} content={<div style={{ maxWidth: 360 }}>{simulation.note}</div>}><Button type="text" size="small">计算说明</Button></Popover>
      </div>

      <div className="result-summary-grid">
        <div><span>初始裂隙压力</span><b>{simulation.summary?.initialFracturePressureMPa} MPa</b></div>
        <div><span>最终裂隙压力</span><b>{simulation.summary?.finalFracturePressureMPa} MPa</b></div>
        <div><span>最终甲烷浓度</span><b>{simulation.summary?.finalMethaneConcentrationPct} %</b></div>
        <div><span>最终流量</span><b>{simulation.summary?.finalFlowM3PerDay} m³/d</b></div>
      </div>

      <div className="result-chart"><ReactECharts option={option} style={{ height: '100%' }} /></div>
      <div className="result-table-wrap" ref={tableRef}>
        <Table
          rowKey="day"
          size="small"
          pagination={false}
          columns={columns}
          dataSource={values}
          scroll={{ x: 950, y: tableHeight }}
        />
      </div>
    </div>
  );
}
