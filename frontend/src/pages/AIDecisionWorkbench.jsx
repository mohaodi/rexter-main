import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert, App, Button, Card, Col, Descriptions, Empty, Input, InputNumber,
  Progress, Row, Select, Space, Statistic, Steps, Table, Tag, Tabs, Upload,
} from 'antd';
import {
  CheckCircleOutlined, CloudUploadOutlined, DatabaseOutlined,
  SafetyCertificateOutlined, SearchOutlined, LineChartOutlined,
} from '@ant-design/icons';
import ReactECharts from 'echarts-for-react';
import request from '../api/request';
import '../styles/ai-workbench.css';

const DEFAULT_PRESSURES = [103518, 62249, 45265, 47045, 64469];
const stageOptions = ['采前', '采中', '采后'].map((value) => ({ value, label: value }));
const number = (value, digits = 2) => {
  const precision = Number.isInteger(digits) ? Math.min(8, Math.max(0, digits)) : 2;
  return Number(value || 0).toLocaleString('zh-CN', { maximumFractionDigits: precision });
};

export default function AIDecisionWorkbench() {
  const { message } = App.useApp();
  const [activeTab, setActiveTab] = useState('data');
  const [status, setStatus] = useState(null);
  const [quality, setQuality] = useState(null);
  const [qualityLoading, setQualityLoading] = useState(false);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState(null);
  const [borehole, setBorehole] = useState('W1');
  const [horizon, setHorizon] = useState(6);
  const [forecast, setForecast] = useState(null);
  const [forecastField, setForecastField] = useState('methanePct');
  const [forecastLoading, setForecastLoading] = useState(false);
  const [anomalies, setAnomalies] = useState(null);
  const [anomalyLoading, setAnomalyLoading] = useState(false);
  const [pressures, setPressures] = useState(DEFAULT_PRESSURES);
  const [stage, setStage] = useState('采中');
  const [boreholeCount, setBoreholeCount] = useState(3);
  const [inclination, setInclination] = useState(20);
  const [spacing, setSpacing] = useState(30);
  const [length, setLength] = useState(120);
  const [pressureRange, setPressureRange] = useState([15, 35]);
  const [methaneMin, setMethaneMin] = useState(60);
  const [flowMin, setFlowMin] = useState(2);
  const [minFit, setMinFit] = useState(80);
  const [candidates, setCandidates] = useState(null);
  const [planLoading, setPlanLoading] = useState(false);
  const [selectedReview, setSelectedReview] = useState(null);
  const [reviewDecision, setReviewDecision] = useState('accepted');
  const [reviewComment, setReviewComment] = useState('');
  const [reviews, setReviews] = useState([]);
  const [reviewLoading, setReviewLoading] = useState(false);

  const loadStatus = useCallback(async () => {
    const result = await Promise.all([request.get('/ai/status'), request.get('/ai/quality')]);
    setStatus(result[0].data);
    setQuality(result[1].data);
  }, []);

  const loadReviews = useCallback(async () => {
    const result = await request.get('/ai/shadow-review', { params: { limit: 30 } });
    setReviews(result.data.items || []);
  }, []);

  useEffect(() => {
    loadStatus().catch((err) => message.error(err?.response?.data?.detail || 'AI工作台初始化失败'));
    loadReviews().catch(() => {});
  }, [loadReviews, loadStatus, message]);

  const refreshQuality = async () => {
    setQualityLoading(true);
    try { await loadStatus(); message.success('数据接入状态与质量报告已更新'); }
    catch (err) { message.error(err?.response?.data?.detail || '质量检查失败'); }
    finally { setQualityLoading(false); }
  };

  const importCsv = async (file) => {
    setImporting(true);
    setImportResult(null);
    try {
      const form = new FormData();
      form.append('file', file);
      const result = await request.post('/ai/data/import-csv', form, { timeout: 120000 });
      setImportResult(result.data);
      await loadStatus();
      message.success('已导入 ' + result.data.insertedRows + ' 条记录');
    } catch (err) {
      message.error(err?.response?.data?.detail || '监测CSV导入失败');
    } finally { setImporting(false); }
    return false;
  };

  const downloadTemplate = () => {
    const content = '\ufeff采集时间,钻孔编号,负压kPa,甲烷浓度,混合流量,纯流量,储层压力MPa,温度,阀门开度,泵功率,生命周期\r\n2026-10-15T09:00:00+08:00,W1,24.5,82.1,4.2,3.45,1.52,23.5,68,42,采中\r\n';
    const url = URL.createObjectURL(new Blob([content], { type: 'text/csv;charset=utf-8' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = '煤系气监测数据模板.csv';
    link.click();
    URL.revokeObjectURL(url);
  };

  const runForecast = async () => {
    setForecastLoading(true);
    try {
      const result = await request.post('/ai/forecast', { boreholeCode: borehole, horizon: horizon, samples: 120 });
      setForecast(result.data);
      if (!result.data.ok) message.warning(result.data.message);
    } catch (err) { message.error(err?.response?.data?.detail || '短期趋势计算失败'); }
    finally { setForecastLoading(false); }
  };

  const runAnomalies = async () => {
    setAnomalyLoading(true);
    try { setAnomalies((await request.post('/ai/anomalies', { samples: 120 })).data); }
    catch (err) { message.error(err?.response?.data?.detail || '异常筛查失败'); }
    finally { setAnomalyLoading(false); }
  };

  const generateCandidates = async () => {
    setPlanLoading(true);
    try {
      const result = await request.post('/ai/plans', {
        pressuresPa: pressures, lifecycleStage: stage, boreholeCount: boreholeCount,
        inclinationDeg: inclination, spacingM: spacing, lengthM: length,
        pressureMinKPa: pressureRange[0], pressureMaxKPa: pressureRange[1],
        methaneMinPct: methaneMin, flowMinM3Min: flowMin, minFitScorePct: minFit,
      }, { timeout: 120000 });
      setCandidates(result.data);
      setSelectedReview(null);
      if (result.data.feasibleCount === 0) message.warning('当前演示边界下没有通过筛查的候选方案');
      else message.success('生成 ' + result.data.candidates.length + ' 个候选，' + result.data.feasibleCount + ' 个通过演示筛查');
    } catch (err) { message.error(err?.response?.data?.detail || '候选方案筛选失败'); }
    finally { setPlanLoading(false); }
  };

  const openReview = (type, id, item) => {
    setSelectedReview({ type: type, id: id, item: item });
    setReviewDecision('accepted');
    setReviewComment('');
    setActiveTab('review');
  };

  const submitReview = async () => {
    if (!selectedReview) return;
    setReviewLoading(true);
    try {
      await request.post('/ai/shadow-review', {
        itemType: selectedReview.type, itemId: selectedReview.id,
        decision: reviewDecision, comment: reviewComment, item: selectedReview.item,
      });
      await loadReviews();
      message.success('人工复核记录已保存；未向现场设备下发');
      setSelectedReview(null);
      setReviewComment('');
    } catch (err) { message.error(err?.response?.data?.detail || '复核记录保存失败'); }
    finally { setReviewLoading(false); }
  };

  const forecastSeries = useMemo(() => {
    if (!forecast?.ok) return [];
    return Object.entries(forecast.variables).map(([key, variable]) => ({
      name: variable.label, key: key, current: variable.current, forecast: variable.forecast,
      lower: variable.lowerBand || variable.lower95, upper: variable.upperBand || variable.upper95, rmse: variable.rollingRmse, unit: variable.unit,
    }));
  }, [forecast]);

  const selectedForecastSeries = forecastSeries.find((series) => series.key === forecastField) || forecastSeries[0];
  const hasForecastBand = Boolean(selectedForecastSeries?.lower?.length && selectedForecastSeries?.upper?.length);
  const chartOption = useMemo(() => ({
    animation: false,
    tooltip: { trigger: 'axis', formatter: (items) => {
      const point = items.find((item) => item.seriesName === selectedForecastSeries?.name);
      if (!point) return '';
      const index = point.dataIndex;
      return `${selectedForecastSeries.name}<br/>${forecast.forecastTimes[index]} s<br/>预测：${number(selectedForecastSeries.forecast[index], 3)} ${selectedForecastSeries.unit}<br/>滚动误差参考带：${number(selectedForecastSeries.lower[index], 3)}–${number(selectedForecastSeries.upper[index], 3)} ${selectedForecastSeries.unit}`;
    } },
    legend: { data: selectedForecastSeries ? [selectedForecastSeries.name] : [], textStyle: { color: '#c6d9e6' } },
    grid: { left: 54, right: 22, top: 48, bottom: 34 },
    xAxis: { type: 'category', data: forecast?.forecastTimes?.map((time) => time + ' s') || [], axisLabel: { color: '#8ea9bb' } },
    yAxis: { type: 'value', name: selectedForecastSeries?.unit, axisLabel: { color: '#8ea9bb' }, splitLine: { lineStyle: { color: '#1c3c50' } } },
    series: hasForecastBand ? [
      { name: '误差区间基线', type: 'line', stack: 'forecast-band', data: selectedForecastSeries.lower, symbol: 'none', lineStyle: { opacity: 0 }, areaStyle: { opacity: 0 }, emphasis: { disabled: true }, tooltip: { show: false } },
      { name: '95%误差区间', type: 'line', stack: 'forecast-band', data: selectedForecastSeries.upper.map((value, index) => value - selectedForecastSeries.lower[index]), symbol: 'none', lineStyle: { opacity: 0 }, areaStyle: { color: 'rgba(49, 166, 213, .22)' }, emphasis: { disabled: true }, tooltip: { show: false } },
      { name: selectedForecastSeries.name, type: 'line', data: selectedForecastSeries.forecast, smooth: true, symbolSize: 5, lineStyle: { width: 2 } },
    ] : [],
  }), [forecast, hasForecastBand, selectedForecastSeries]);

  const dataTab = <div className="ai-tab-content ai-data-content">
    <Alert showIcon type="warning" message="现场通讯接口待配置" description={status?.disclaimer || '导入数据用于原型验证；OPC UA、Modbus及PLC控制需现场协议、点表、安全审批与联调。'} />
    <Row gutter={10} className="ai-kpis">
      <Col span={6}><Card><Statistic title="数据库记录" value={quality?.recordCount ?? 0} suffix="条" /></Card></Col>
      <Col span={6}><Card><Statistic title="数据质量指数" value={quality?.qualityScore ?? 0} precision={1} suffix="分" /></Card></Col>
      <Col span={6}><Card><Statistic title="覆盖钻孔" value={quality?.wellCount ?? 0} suffix="孔" /></Card></Col>
      <Col span={6}><Card><Statistic title="异常数据标记" value={quality?.warningRecords ?? 0} suffix="条" /></Card></Col>
    </Row>
    <Row gutter={12} className="ai-main-row">
      <Col span={14}>
        <Card title="数据质量检查" extra={<Button size="small" loading={qualityLoading} onClick={refreshQuality}>刷新检查</Button>} className="ai-fill-card">
          {!quality ? <Empty description="正在读取监测数据" /> : <>
            <Descriptions size="small" column={2}>
              <Descriptions.Item label="来源分布">{Object.entries(quality.bySource || {}).map(([key, value]) => <Tag key={key}>{key}: {value}</Tag>)}</Descriptions.Item>
              <Descriptions.Item label="最近记录">{quality.latestAt || '--'}</Descriptions.Item>
            </Descriptions>
            <Table size="small" pagination={false} rowKey="name" dataSource={quality.checks || []} columns={[
              { title: '检查项', dataIndex: 'name' },
              { title: '结果', dataIndex: 'passed', render: (value) => <Tag color={value ? 'green' : 'orange'}>{value ? '通过' : '待检查'}</Tag> },
              { title: '说明', dataIndex: 'detail' },
            ]} />
            <p className="ai-note">{quality.scoreNote}</p>
          </>}
        </Card>
      </Col>
      <Col span={10}>
        <Card title="数据接入" className="ai-fill-card">
          <div className="ai-connector-list">
            {(status?.connectors || []).map((item) => <div className="ai-connector" key={item.id}>
              <div><b>{item.name}</b><small>{item.status === 'ready' ? item.note : item.missing}</small></div>
              <Tag color={item.status === 'ready' ? 'green' : item.status === 'disabled' ? 'default' : 'gold'}>{item.status === 'ready' ? '可用' : item.status === 'disabled' ? '禁用' : '待配置'}</Tag>
            </div>)}
          </div>
          <Space wrap className="ai-import-actions">
            <Upload accept=".csv,text/csv" showUploadList={false} beforeUpload={importCsv}>
              <Button icon={<CloudUploadOutlined />} loading={importing}>导入监测CSV</Button>
            </Upload>
            <Button onClick={downloadTemplate}>下载CSV模板</Button>
          </Space>
          {importResult && <Alert className="ai-import-result" type={importResult.rejectedRows ? 'warning' : 'success'} showIcon message={'导入' + importResult.insertedRows + '条，拒绝' + importResult.rejectedRows + '条'} description={importResult.note} />}
        </Card>
      </Col>
    </Row>
  </div>;

  const forecastTab = <div className="ai-tab-content ai-forecast-content">
    <div className="ai-toolbar">
      <Space wrap>
        <Select value={borehole} onChange={setBorehole} options={[1, 2, 3, 4, 5].map((i) => ({ value: 'W' + i, label: '钻孔 W' + i }))} />
        <span>预测步数</span><InputNumber min={1} max={12} value={horizon} onChange={(v) => setHorizon(v || 6)} />
        <Button type="primary" loading={forecastLoading} onClick={runForecast}>运行短期趋势预测</Button>
      </Space>
      <Tag color="blue">数据驱动基线 · 滚动留出误差区间</Tag>
    </div>
    {!forecast ? <Empty description="选择钻孔并运行预测" /> : !forecast.ok ? <Alert type="warning" showIcon message="当前钻孔历史数据不足" description={forecast.message} /> : <>
      <Alert showIcon type="info" message={forecast.boreholeCode + '：基于' + forecast.historyCount + '条历史记录，按约' + forecast.sampleIntervalSeconds.toFixed(0) + '秒采样间隔预测'} description={forecast.disclaimer} />
      <Row gutter={12} className="ai-forecast-row">
        <Col span={14}><Card title={<Space>短期趋势与滚动误差参考带<Select value={forecastField} onChange={setForecastField} options={forecastSeries.map((series) => ({ value: series.key, label: series.name }))} /></Space>} className="ai-fill-card"><ReactECharts option={chartOption} style={{ height: '100%', minHeight: 260 }} /></Card></Col>
        <Col span={10}><Card title="预测值与滚动误差" className="ai-fill-card"><Table size="small" pagination={false} scroll={{ y: 290 }} rowKey="key" dataSource={forecastSeries} columns={[
          { title: '指标', dataIndex: 'name' }, { title: '当前值', dataIndex: 'current', render: (v) => number(v) },
          { title: '末步预测', render: (_, row) => number(row.forecast[row.forecast.length - 1]) },
          { title: '留出RMSE', dataIndex: 'rmse', render: (v) => number(v, 3) },
        ]} /></Card></Col>
      </Row>
      <div className="ai-tab-footer"><span>{forecast.model}。{forecast.validation}</span><Button onClick={() => openReview('forecast', forecast.boreholeCode + ':' + Date.now(), forecast)}>送入人工影子复核</Button></div>
    </>}
  </div>;

  const anomalyColumns = [
    { title: '时间', dataIndex: 'recordedAt', width: 180 },
    { title: '钻孔', dataIndex: 'boreholeCode', width: 72 },
    { title: '指标', dataIndex: 'label', width: 110 },
    { title: '观测值', render: (_, row) => row.value + ' ' + row.unit },
    { title: '级别', dataIndex: 'severity', render: (v) => <Tag color={v === 'critical' ? 'red' : 'orange'}>{v === 'critical' ? '范围越界' : '需复核'}</Tag> },
    { title: '识别依据', dataIndex: 'reason' },
    { title: '操作', render: (_, row) => <Button size="small" onClick={() => openReview('anomaly', row.id, row)}>人工复核</Button> },
  ];
  const anomalyTab = <div className="ai-tab-content ai-anomaly-content">
    <div className="ai-toolbar"><Space><Button type="primary" icon={<SearchOutlined />} loading={anomalyLoading} onClick={runAnomalies}>执行异常检测</Button><Tag>窗口：最近120条</Tag></Space><Tag color="gold">规则边界 + MAD稳健偏离 + 流量一致性</Tag></div>
    {!anomalies ? <Empty description="运行检测后查看异常信号及其判定依据" /> : <>
      <Row gutter={10} className="ai-kpis"><Col span={8}><Card><Statistic title="检查记录" value={anomalies.windowRecords} suffix="条" /></Card></Col><Col span={8}><Card><Statistic title="检查点" value={anomalies.monitoredPoints} /></Card></Col><Col span={8}><Card><Statistic title="待复核信号" value={anomalies.anomalyCount} valueStyle={{ color: anomalies.anomalyCount ? '#e2a64b' : '#42c98a' }} /></Card></Col></Row>
      <Alert showIcon type="warning" message="异常信号为原型筛查结果" description={anomalies.disclaimer} />
      <Card title="检测发现" className="ai-anomaly-table"><Table size="small" rowKey="id" pagination={{ pageSize: 8, size: 'small' }} scroll={{ x: 1000, y: 330 }} locale={{ emptyText: <Empty description="当前窗口未发现超出演示边界的异常" /> }} dataSource={anomalies.findings} columns={anomalyColumns} /></Card>
    </>}
  </div>;

  const planTab = <div className="ai-tab-content ai-plan-content">
    <div className="ai-plan-layout">
      <Card title="抽采目标与安全约束" className="ai-plan-form">
        <div className="ai-pressure-inputs">{pressures.map((value, index) => <label key={index}><span>W{index + 1}目标压力</span><InputNumber value={value} min={1000} max={200000} addonAfter="Pa" onChange={(v) => setPressures((old) => old.map((x, i) => i === index ? Number(v || 0) : x))} /></label>)}</div>
        <div className="ai-plan-fields">
          <label>生命周期<Select value={stage} onChange={setStage} options={stageOptions} /></label>
          <label>钻孔数<InputNumber min={1} max={9} value={boreholeCount} onChange={(v) => setBoreholeCount(v || 3)} /></label>
          <label>倾角 °<InputNumber min={5} max={45} value={inclination} onChange={(v) => setInclination(v || 20)} /></label>
          <label>孔间距 m<InputNumber min={10} max={50} value={spacing} onChange={(v) => setSpacing(v || 30)} /></label>
          <label>孔长 m<InputNumber min={40} max={260} value={length} onChange={(v) => setLength(v || 120)} /></label>
          <label>负压下限 kPa<InputNumber min={0} max={pressureRange[1] - 0.1} value={pressureRange[0]} onChange={(v) => setPressureRange([Number(v || 0), pressureRange[1]])} /></label>
          <label>负压上限 kPa<InputNumber min={pressureRange[0] + 0.1} max={95} value={pressureRange[1]} onChange={(v) => setPressureRange([pressureRange[0], Number(v || 35)])} /></label>
          <label>甲烷下限 %<InputNumber min={0} max={100} value={methaneMin} onChange={(v) => setMethaneMin(v ?? 60)} /></label>
          <label>混流下限 m³/min<InputNumber min={0} value={flowMin} onChange={(v) => setFlowMin(v ?? 2)} /></label>
          <label>拟合门槛 %<InputNumber min={0} max={100} value={minFit} onChange={(v) => setMinFit(v ?? 80)} /></label>
        </div>
        <Button type="primary" block loading={planLoading} onClick={generateCandidates}>生成并筛查三类候选方案</Button>
        <p className="ai-note">压力预测来自现有Attention-LSTM/PSO；几何条件在工程层枚举并筛查。边界为演示条件，需矿区规程与测量数据校准。</p>
      </Card>
      <div className="ai-plan-results">
        {!candidates ? <Card className="ai-fill-card"><Empty description="设置目标与边界后，生成候选方案" /></Card> : <>
          <Alert showIcon type={candidates.feasibleCount ? 'success' : 'warning'} message={'通过演示筛查 ' + candidates.feasibleCount + '/' + candidates.candidates.length + ' 个候选方案'} description={candidates.modelBoundary + ' ' + candidates.constraintSource} />
          <div className="ai-candidate-grid">{candidates.candidates.map((candidate) => <Card key={candidate.schemeCode} title={candidate.candidateName} extra={<Tag color={candidate.feasible ? 'green' : 'red'}>{candidate.safetyStatus}</Tag>} className="ai-candidate-card">
            <div className="ai-candidate-metrics"><span>拟合度 <b>{candidate.metrics.fitScorePct.toFixed(2)}%</b></span><span>MAE <b>{number(candidate.metrics.maePa, 1)} Pa</b></span><span>RMSE <b>{number(candidate.metrics.rmsePa, 1)} Pa</b></span></div>
            <div className="ai-candidate-params">{candidate.boreholes.length}孔 · {candidate.boreholes[0]?.inclinationDeg}° · {candidate.boreholes[0]?.spacingM}m间距 · {candidate.boreholes[0]?.lengthM}m</div>
            <div className="ai-well-pressure-list">{candidate.boreholes.map((well) => <span key={well.code}>{well.code} <b>{number(well.extractionPressureKPa, 2)} kPa</b></span>)}</div>
            <Table size="small" pagination={false} showHeader={false} rowKey="name" dataSource={candidate.safetyChecks} columns={[{ dataIndex: 'name' }, { dataIndex: 'passed', render: (v) => <Tag color={v ? 'green' : 'red'}>{v ? '通过' : '未通过'}</Tag> }]} />
            <Button size="small" onClick={() => openReview('plan', candidate.schemeCode, candidate)}>送入人工复核</Button>
          </Card>)}</div>
        </>}
      </div>
    </div>
  </div>;

  const reviewTab = <div className="ai-tab-content ai-review-content">
    <Row gutter={12} className="ai-main-row">
      <Col span={10}><Card title="影子运行边界" className="ai-fill-card"><Steps direction="vertical" size="small" current={1} items={[
        { title: '历史/模拟数据回放', description: '当前已具备；记录来源与质量。' },
        { title: '模型输出与人工复核', description: '当前可记录采纳、驳回或调整意见。' },
        { title: '现场旁路对照', description: '待矿方实时只读接口及专家签审。' },
        { title: '受控联锁与审计', description: '待安全论证、授权、联锁测试和现场验收。' },
      ]} /><Alert className="ai-review-alert" type="warning" showIcon message="影子验证只记录意见，不执行控制" description="进入现场前需完成数据授权、阈值审定、基线对照、漏报/误报评价和安全审批。" /></Card></Col>
      <Col span={14}><Card title="本次输出复核" className="ai-fill-card">
        {!selectedReview ? <Empty description="从预测、异常或方案页选择一条结果送入复核" /> : <>
          <Descriptions size="small" column={1} bordered><Descriptions.Item label="类型">{({ forecast: '趋势预测', anomaly: '异常信号', plan: '候选方案' })[selectedReview.type]}</Descriptions.Item><Descriptions.Item label="对象">{selectedReview.id}</Descriptions.Item><Descriptions.Item label="判定状态">仅作影子复核，不会写入设备</Descriptions.Item></Descriptions>
          <Space className="ai-review-decision" wrap>
            <Select value={reviewDecision} onChange={setReviewDecision} options={[{ value: 'accepted', label: '采纳' }, { value: 'rejected', label: '驳回' }, { value: 'adjusted', label: '调整后采纳' }]} />
            <Input value={reviewComment} onChange={(e) => setReviewComment(e.target.value)} placeholder="填写依据或需要补充的现场信息" maxLength={1000} />
            <Button type="primary" loading={reviewLoading} onClick={submitReview}>保存复核记录</Button>
          </Space>
        </>}
      </Card></Col>
    </Row>
    <Card title="历史复核记录" className="ai-review-history"><Table size="small" rowKey="id" pagination={{ pageSize: 6, size: 'small' }} scroll={{ y: 230 }} dataSource={reviews} columns={[
      { title: '时间', dataIndex: 'created_at', width: 190 }, { title: '类型', dataIndex: 'item_type', render: (v) => ({ forecast: '预测', anomaly: '异常', plan: '方案' })[v] || v },
      { title: '对象', dataIndex: 'item_id' }, { title: '人工结论', dataIndex: 'decision', render: (v) => ({ accepted: '采纳', rejected: '驳回', adjusted: '调整后采纳' })[v] || v }, { title: '备注', dataIndex: 'comment' },
    ]} /></Card>
  </div>;

  const tabs = [
    { key: 'data', label: <span><DatabaseOutlined /> 数据接入与质量</span>, children: dataTab },
    { key: 'forecast', label: <span><LineChartOutlined /> 趋势预测</span>, children: forecastTab },
    { key: 'anomaly', label: <span><SearchOutlined /> 异常检测</span>, children: anomalyTab },
    { key: 'plans', label: <span><SafetyCertificateOutlined /> 安全约束方案</span>, children: planTab },
    { key: 'review', label: <span><CheckCircleOutlined /> 影子验证与反馈</span>, children: reviewTab },
  ];

  return <div className="ai-workbench-page">
    <header className="ai-workbench-head">
      <div><h1>AI安全决策工作台</h1><p>数据接入 · 趋势预测 · 异常筛查 · 方案约束 · 人工影子验证</p></div>
      <Space wrap><Tag color={status?.liveAdapterConnected ? 'green' : 'gold'}>{status?.liveAdapterConnected ? '含导入数据' : '模拟数据源'}</Tag><Tag color="blue">只读建议</Tag><Button icon={<CheckCircleOutlined />} onClick={() => setActiveTab('review')}>影子验证记录</Button></Space>
    </header>
    <Tabs activeKey={activeTab} onChange={setActiveTab} className="ai-workbench-tabs" items={tabs} />
  </div>;
}
