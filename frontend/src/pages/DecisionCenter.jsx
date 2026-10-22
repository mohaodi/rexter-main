import React, { useState } from 'react';
import { App, Button, Card, Empty, Popover, Progress, Table, Tag } from 'antd';
import request from '../api/request';
import '../styles/platform.css';

export default function DecisionCenter() {
  const { message } = App.useApp();
  const [loading, setLoading] = useState(false);
  const [recommending, setRecommending] = useState(false);
  const [diagnosis, setDiagnosis] = useState(null);
  const [assessment, setAssessment] = useState(null);
  const [advice, setAdvice] = useState(null);
  const load = async () => {
    setLoading(true);
    try {
      const [d, a] = await Promise.all([request.get('/platform/diagnosis'), request.get('/platform/assessment')]);
      setDiagnosis(d.data);
      setAssessment(a.data);
    } catch (err) {
      message.error(err?.response?.data?.detail || '诊断与评判获取失败');
    } finally { setLoading(false); }
  };
  const recommend = async () => {
    setRecommending(true);
    try { setAdvice((await request.post('/platform/control/advice')).data); }
    catch (err) { message.error(err?.response?.data?.detail || '调控建议生成失败'); }
    finally { setRecommending(false); }
  };
  return (
    <div className="platform-page decision-page">
      <div className="platform-head">
        <div><h1>智能调控、诊断与达标评判</h1><p>运行状态诊断 · 抽采指标评判 · 多钻孔协同调控</p></div>
        <div className="decision-actions"><Button loading={loading} onClick={load}>刷新诊断与评判</Button> <Button type="primary" loading={recommending} onClick={recommend}>生成协同调控建议</Button><Popover title="调控说明" content={<div style={{ maxWidth: 320 }}>当前生成协同调控建议，不直接下发设备指令。未提供算法权重的部分采用规则约束演示层。</div>}><Button type="text">调控说明</Button></Popover></div>
      </div>
      <div className="decision-grid">
        <Card title="智能诊断">
          {!diagnosis ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="刷新诊断与评判，查看运行状态" /> : <>
            <Tag color={diagnosis.status === 'normal' ? 'green' : 'orange'}>{diagnosis.status === 'normal' ? '运行正常' : diagnosis.status}</Tag>
            <p>{diagnosis.method}</p>
            <Table size="small" pagination={false} locale={{emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="未检测到异常" />}} dataSource={(diagnosis.findings || []).map((x, i) => ({ ...x, key: i }))}
              columns={[{ title: '钻孔', dataIndex: 'boreholeCode' }, { title: '类型', dataIndex: 'type' }, { title: '处理建议', dataIndex: 'message' }]} />
          </>}
        </Card>
        <Card title="抽采达标自动评判">
          {!assessment ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="刷新诊断与评判，查看指标结果" /> : <>
            <div className="assessment-layout"><Progress type="dashboard" size={100} percent={assessment.score} status={assessment.compliant ? 'success' : 'normal'} />
            <Table size="small" pagination={false} dataSource={assessment.checks.map((x, i) => ({ ...x, key: i }))}
              columns={[{ title: '指标', dataIndex: 'name' }, { title: '值', render: (_, r) => String(r.value) + ' ' + r.unit }, { title: '阈值', dataIndex: 'threshold' }, { title: '结果', dataIndex: 'passed', render: (v) => <Tag color={v ? 'green' : 'red'}>{v ? '通过' : '未通过'}</Tag> }]} />
            </div><p className="caution-text">{assessment.basis}</p>
          </>}
        </Card>
      <Card title="多钻孔协同调控建议" className="advice-card" extra={<Popover title="建议依据与执行说明" content={<div style={{maxWidth:360}}>{advice?.notice || '建议供人工复核，不直接下发设备指令。'}</div>}><Tag color="cyan">建议模式 · 说明</Tag></Popover>}>
        {!advice ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="生成协同调控建议，查看五钻孔推荐参数" /> : <>
          <Table size="small" rowKey="boreholeCode" pagination={false} scroll={{ x: 680 }} dataSource={advice.commands}
            columns={[
              { title: '钻孔', dataIndex: 'boreholeCode' },
              { title: '当前负压/kPa', dataIndex: 'currentPressureKPa' },
              { title: '建议负压/kPa', dataIndex: 'recommendedPressureKPa' },
              { title: '建议阀门/%', dataIndex: 'recommendedValveOpenPct' },
              { title: '依据', dataIndex: 'reason' },
            ]} />
        </>}
      </Card>
      </div>
    </div>
  );
}
