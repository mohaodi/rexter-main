import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Button, Card, Col, Row, Select, Space, Statistic, Table, Tag } from 'antd';
import ReactECharts from 'echarts-for-react';
import request from '../api/request';
import '../styles/platform.css';

export default function RealtimePlatform() {
  const [stage, setStage] = useState('采中');
  const [snapshot, setSnapshot] = useState([]);
  const [history, setHistory] = useState([]);
  const [selected, setSelected] = useState('W1');
  const [running, setRunning] = useState(true);
  const [db, setDb] = useState(null);
  const refresh = useCallback(async (write = false) => {
    const snap = write
      ? await request.post('/platform/realtime/tick', { lifecycleStage: stage })
      : await request.get('/platform/realtime/snapshot', { params: { stage } });
    setSnapshot(snap.data.items || []);
    const curve = await request.get('/platform/realtime/history', { params: { borehole: selected, limit: 120 } });
    setHistory(curve.data.items || []);
    request.get('/platform/database/status').then((r) => setDb(r.data)).catch(() => {});
  }, [selected, stage]);
  useEffect(() => { refresh(false); }, [refresh]);
  useEffect(() => {
    if (!running) return undefined;
    const timer = setInterval(() => refresh(true), 3000);
    return () => clearInterval(timer);
  }, [refresh, running]);
  const sums = useMemo(() => ({
    pure: snapshot.reduce((a, x) => a + Number(x.pureFlowM3Min || 0), 0),
    power: snapshot.reduce((a, x) => a + Number(x.pumpPowerKW || 0), 0),
    methane: snapshot.length ? snapshot.reduce((a, x) => a + Number(x.methanePct || 0), 0) / snapshot.length : 0,
    pressure: snapshot.length ? snapshot.reduce((a, x) => a + Number(x.negativePressureKPa || 0), 0) / snapshot.length : 0,
  }), [snapshot]);
  const option = {
    tooltip: { trigger: 'axis' },
    legend: { data: ['负压/kPa', '浓度/%', '纯量/m³·min⁻¹'], textStyle: { color: '#b9cbd8' } },
    grid: { left: 58, right: 55, top: 45, bottom: 45 },
    xAxis: { type: 'category', data: history.map((x) => x.recordedAt?.slice(11, 19)), axisLabel: { color: '#829caf' } },
    yAxis: [{ type: 'value', axisLabel: { color: '#829caf' }, splitLine: { lineStyle: { color: '#173247' } } }, { type: 'value', axisLabel: { color: '#829caf' } }],
    series: [
      { name: '负压/kPa', type: 'line', showSymbol: false, data: history.map((x) => x.negativePressureKPa) },
      { name: '浓度/%', type: 'line', yAxisIndex: 1, showSymbol: false, data: history.map((x) => x.methanePct) },
      { name: '纯量/m³·min⁻¹', type: 'line', showSymbol: false, data: history.map((x) => x.pureFlowM3Min) },
    ],
  };
  return (
    <div className="platform-page realtime-page">
      <div className="platform-head">
        <div><h1>实时监测与数据库</h1><p>五钻孔抽采状态 · 历史趋势追踪 · 数据库同步</p></div>
        <Space wrap>
          <Tag color="cyan">模拟数据源</Tag>
          <Tag color={db?.connected ? 'green' : 'red'}>{db?.engine || '--'} · {db?.sensorRows || 0} 条</Tag>
          <Select value={stage} onChange={setStage} options={['采前', '采中', '采后'].map((x) => ({ value: x, label: x }))} />
          <Button onClick={() => setRunning(!running)}>{running ? '暂停模拟' : '继续模拟'}</Button>
        </Space>
      </div>
      <Row gutter={12} className="metric-row">
        <Col span={6}><Card><Statistic title="平均负压" value={sums.pressure} precision={2} suffix="kPa" /></Card></Col>
        <Col span={6}><Card><Statistic title="平均浓度" value={sums.methane} precision={2} suffix="%" /></Card></Col>
        <Col span={6}><Card><Statistic title="五孔纯量" value={sums.pure} precision={2} suffix="m³/min" /></Card></Col>
        <Col span={6}><Card><Statistic title="泵功率合计" value={sums.power} precision={1} suffix="kW" /></Card></Col>
      </Row>
      <div className="platform-two">
        <Card title="五钻孔最新状态" extra={<span className="muted">点击钻孔查看趋势</span>}>
          <Table rowKey="boreholeCode" pagination={false} size="small" scroll={{ x: 440 }} dataSource={snapshot} rowClassName={(r) => r.boreholeCode === selected ? 'selected-well' : ''} onRow={(r) => ({ onClick: () => setSelected(r.boreholeCode) })}
            columns={[
              { title: '钻孔', dataIndex: 'boreholeCode', render: (v) => <Tag color={v === selected ? 'blue' : 'default'}>{v}</Tag> },
              { title: '负压/kPa', dataIndex: 'negativePressureKPa' },
              { title: '浓度/%', dataIndex: 'methanePct' },
              { title: '混量', dataIndex: 'mixedFlowM3Min' },
              { title: '纯量', dataIndex: 'pureFlowM3Min' },
              { title: '阀门/%', dataIndex: 'valveOpenPct' },
              { title: '质量', dataIndex: 'qualityFlag', render: (v) => <Tag color={v === 'good' ? 'green' : 'orange'}>{v === 'good' ? '正常' : v}</Tag> },
            ]} />
        </Card>
        <Card title={selected + ' 最近 120 帧演化曲线'} className="realtime-chart-card"><ReactECharts option={option} style={{ height: '100%' }} /></Card>
      </div>
    </div>
  );
}
