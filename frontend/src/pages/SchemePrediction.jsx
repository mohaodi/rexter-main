import React, { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  ConfigProvider,
  theme,
  Col,
  Descriptions,
  Divider,
  Form,
  InputNumber,
  Popover,
  Row,
  Select,
  Space,
  Statistic,
  Table,
  Tabs,
  Tag,
  Typography,
} from 'antd';
import {
  AimOutlined,
  AreaChartOutlined,
  ExperimentOutlined,
  FundProjectionScreenOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import ReactECharts from 'echarts-for-react';
import request from '../api/request';
import SchemeTwin from '../components/SchemeTwin';
import '../styles/scheme-prediction.css';

const { Title, Paragraph, Text } = Typography;

const DEFAULT_PRESSURES = [103518, 62249, 45265, 47045, 64469];

function fmt(value, digits = 2) {
  const n = Number(value);
  if (!Number.isFinite(n)) return '--';
  return n.toLocaleString('zh-CN', { maximumFractionDigits: digits });
}

function SchemeInversePanel() {
  const [pressures, setPressures] = useState(DEFAULT_PRESSURES);
  const [swarmSize, setSwarmSize] = useState(48);
  const [maxIter, setMaxIter] = useState(45);
  const [lifecycleStage, setLifecycleStage] = useState('采前');
  const [boreholeCount, setBoreholeCount] = useState(3);
  const [inclinationDeg, setInclinationDeg] = useState(20);
  const [spacingM, setSpacingM] = useState(30);
  const [lengthM, setLengthM] = useState(120);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  const run = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await request.post('/scheme/recommend', {
        pressuresPa: pressures.map(Number),
        swarmSize,
        maxIter,
        seed: 42,
        lifecycleStage,
        boreholeCount,
        inclinationDeg,
        spacingM,
        lengthM,
      });
      setResult(res.data);
    } catch (e) {
      setError(e?.response?.data?.detail || e.message || '方案预测失败');
    } finally {
      setLoading(false);
    }
  };

  const pressureRows = useMemo(() => {
    if (!result) return [];
    return pressures.map((target, i) => ({
      key: i,
      well: `W${i + 1}`,
      target,
      predicted: result.predictedPressuresPa?.[i],
      residual: result.residualPressuresPa?.[i],
    }));
  }, [result, pressures]);

  const chartOption = useMemo(() => ({
    tooltip: { trigger: 'axis' },
    legend: { data: ['目标压力', '方案预测压力'], textStyle: { color: '#39566b' } },
    grid: { left: 58, right: 24, top: 52, bottom: 42 },
    xAxis: { type: 'category', data: ['W1', 'W2', 'W3', 'W4', 'W5'] },
    yAxis: { type: 'value', name: '压力 / Pa', axisLabel: { formatter: (v) => `${Math.round(v / 1000)}k` } },
    series: [
      { name: '目标压力', type: 'bar', data: pressures, barMaxWidth: 28 },
      { name: '方案预测压力', type: 'line', data: result?.predictedPressuresPa || [], smooth: true, symbolSize: 8 },
    ],
  }), [pressures, result]);

  const scheme = result?.scheme || {};

  return (
    <div className="scheme-workbench">
      <section className="scheme-control-panel research-panel">
        <div className="panel-title"><AimOutlined /> 目标状态与方案搜索
          <Popover title="方案搜索说明" content={<div style={{maxWidth:320}}>当前模块用于方案筛选与参数反演，不直接向现场设备下发控制命令；推荐结果需结合现场约束和物理仿真进一步校核。</div>}><Button type="text" size="small">说明</Button></Popover>
        </div>
        <div className="well-pressure-grid">
          {pressures.map((v, i) => (
            <label key={i} className="well-pressure-item">
              <span>W{i + 1} 目标压力</span>
              <InputNumber
                value={v}
                min={1000}
                max={200000}
                step={500}
                addonAfter="Pa"
                onChange={(value) => {
                  const next = [...pressures];
                  next[i] = Number(value || 0);
                  setPressures(next);
                }}
              />
            </label>
          ))}
        </div>

        <Divider />
        <div className="well-pressure-grid">
          <label className="well-pressure-item"><span>生命周期阶段</span>
            <Select value={lifecycleStage} onChange={setLifecycleStage} options={['采前', '采中', '采后'].map((x) => ({ value: x, label: x }))} />
          </label>
          <label className="well-pressure-item"><span>钻孔数量</span>
            <InputNumber min={1} max={9} value={boreholeCount} onChange={(v) => setBoreholeCount(Number(v || 3))} addonAfter="孔" />
          </label>
          <label className="well-pressure-item"><span>倾角</span>
            <InputNumber min={5} max={45} value={inclinationDeg} onChange={(v) => setInclinationDeg(Number(v || 20))} addonAfter="°" />
          </label>
          <label className="well-pressure-item"><span>孔间距</span>
            <InputNumber min={10} max={50} value={spacingM} onChange={(v) => setSpacingM(Number(v || 30))} addonAfter="m" />
          </label>
          <label className="well-pressure-item"><span>钻孔长度</span>
            <InputNumber min={40} max={260} value={lengthM} onChange={(v) => setLengthM(Number(v || 120))} addonAfter="m" />
          </label>
        </div>
        <Divider />
        <Row gutter={12}>
          <Col span={12}>
            <label className="compact-field">粒子群规模
              <InputNumber min={12} max={120} value={swarmSize} onChange={(v) => setSwarmSize(Number(v || 48))} />
            </label>
          </Col>
          <Col span={12}>
            <label className="compact-field">最大迭代次数
              <InputNumber min={5} max={150} value={maxIter} onChange={(v) => setMaxIter(Number(v || 45))} />
            </label>
          </Col>
        </Row>

        <Button type="primary" icon={<ThunderboltOutlined />} block size="large" loading={loading} onClick={run}>
          生成候选抽采方案
        </Button>

        {error && <Alert type="error" showIcon message="方案预测失败" description={error} style={{ marginTop: 14 }} />}

      </section>

      <section className="scheme-result-stack">
        <div className="scheme-upper-grid">
          <Card className="research-panel scheme-twin-card" title="推荐方案三维数字孪生">
            {!result ? <div className="scheme-placeholder">生成方案后显示推荐钻孔轨迹。</div> : <>
              <Space style={{ marginBottom: 8 }} wrap>
                <Tag color="blue">{result.schemeCode}</Tag>
                <Tag>{result.lifecycleStage}</Tag>
                <Tag color="green">工程边界检查</Tag>
              </Space>
              <SchemeTwin boreholes={result.boreholes || []} inclination={result?.scheme?.inclinationDeg || 20} length={result?.scheme?.lengthM || 120}/>
            </>}
          </Card>
          <div className="scheme-right-stack">
            <div className="scheme-kpi-grid">
              <Card><Statistic title="拟合度" value={result?.metrics?.fitScorePct ?? 0} precision={2} suffix="%" /></Card>
              <Card><Statistic title="MAE" value={result?.metrics?.maePa ?? 0} precision={1} suffix="Pa" /></Card>
              <Card><Statistic title="RMSE" value={result?.metrics?.rmsePa ?? 0} precision={1} suffix="Pa" /></Card>
            </div>
            <Card className="research-panel" title="候选方案参数">
              {!result ? <div className="scheme-placeholder">执行方案搜索后显示推荐参数。</div> :
              <div className="scheme-parameter-grid">
                <div><span>修正系数</span><b>{fmt(scheme.correctionCoefficient,4)}</b></div>
                <div><span>储层瓦斯压力</span><b>{fmt(scheme.reservoirGasPressureMPa,4)} MPa</b></div>
                <div><span>抽采压力</span><b>{fmt(scheme.extractionPressureKPa,3)} kPa</b></div>
                <div><span>渗透率</span><b>{fmt(scheme.permeabilityMd,4)} mD</b></div>
                <div><span>开挖距离</span><b>{fmt(scheme.excavationDistanceM,2)} m</b></div>
              </div>}
            </Card>
          </div>
        </div>
        <Card className="research-panel scheme-consistency-card" title="目标状态—方案预测一致性">
          <ReactECharts option={chartOption} style={{height:'100%'}} />
          <Table className="scheme-table-scroll" size="small" pagination={false} scroll={{x:360}} dataSource={pressureRows}
            columns={[
              {title:'钻孔',dataIndex:'well',width:70},
              {title:'目标压力 / Pa',dataIndex:'target',render:v=>fmt(v,0)},
              {title:'预测压力 / Pa',dataIndex:'predicted',render:v=>fmt(v,0)},
              {title:'残差 / Pa',dataIndex:'residual',render:v=>fmt(v,0)}
            ]}/>
        </Card>
      </section>
    </div>
  );
}

function ProductivityPanel() {
  const [startDay, setStartDay] = useState(1501);
  const [endDay, setEndDay] = useState(1800);
  const [modelType, setModelType] = useState('hybrid');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  const run = async () => {
    setLoading(true);
    setError('');
    try {
      // The first request trains and caches the existing BP residual models.
      const res = await request.post('/scheme/productivity', { startDay, endDay, modelType }, { timeout: 300000 });
      setResult(res.data);
    } catch (e) {
      setError(e?.response?.data?.detail || e.message || '产能预测失败');
    } finally {
      setLoading(false);
    }
  };

  const chartOption = useMemo(() => ({
    tooltip: { trigger: 'axis' },
    legend: { data: modelType === 'physical' ? ['物理模型'] : ['物理模型', '物理+BP残差修正'], textStyle: { color: '#39566b' } },
    grid: { left: 70, right: 26, top: 50, bottom: 48 },
    xAxis: { type: 'category', data: result?.days || [], name: '天数', axisLabel: { interval: 'auto' } },
    yAxis: { type: 'value', name: '日产气量' },
    series: [
      { name: '物理模型', type: 'line', data: result?.physicalCurve || [], showSymbol: false, smooth: true },
      ...(modelType === 'physical' ? [] : [{ name: '物理+BP残差修正', type: 'line', data: result?.hybridCurve || [], showSymbol: false, smooth: true }]),
    ],
  }), [result, modelType]);

  return (
    <div className="productivity-layout">
      <Card className="research-panel productivity-control" title="未来产能预测条件">
        <Form layout="vertical">
          <Form.Item label="预测起始天数">
            <InputNumber value={startDay} min={101} onChange={(v) => setStartDay(Number(v || 1501))} addonAfter="d" />
          </Form.Item>
          <Form.Item label="预测终止天数">
            <InputNumber value={endDay} min={startDay + 1} onChange={(v) => setEndDay(Number(v || 1800))} addonAfter="d" />
          </Form.Item>
          <Form.Item label="预测模型">
            <Select value={modelType} onChange={setModelType} options={[
              { value: 'physical', label: '双指数物理衰减模型' },
              { value: 'hybrid', label: '双指数 + BP残差修正' },
              { value: 'compare', label: '双模型对比' },
            ]} />
          </Form.Item>
          <Button type="primary" block size="large" loading={loading} onClick={run}>{loading ? '正在计算产能预测' : '开始产能预测'}</Button>
        </Form>
        {error && <Alert type="error" showIcon message={error} style={{ marginTop: 14 }} />}
        {result?.meta && (
          <div className="model-meta-box">
            <b>模型校核信息</b>
            <span>残差模型：{result.meta.residualModel}</span>
            <span>验证 RMSE：{fmt(result.meta.validationRmse, 2)}</span>
            <span>最优 α：{fmt(result.meta.bestAlpha, 3)}</span>
          </div>
        )}
      </Card>

      <div className="productivity-results">
        <div className="scheme-kpi-grid two">
          <Card><Statistic title="预测末日产气量" value={result?.finalDailyOutput ?? 0} precision={2} /></Card>
          <Card><Statistic title="预测区间累计产量" value={result?.cumulativeOutput ?? 0} precision={2} /></Card>
        </div>
        <Card className="research-panel productivity-chart-card" title="产能演化预测曲线">
          <ReactECharts option={chartOption} style={{ height: '100%' }} />
        </Card>
        <Card className="research-panel productivity-table-card" title="关键时间节点">
          <Table
            size="small"
            pagination={false}
            dataSource={(result?.tableData || []).map((r) => ({ ...r, key: r.day }))}
            columns={[
              { title: '天数', dataIndex: 'day' },
              { title: '物理预测', dataIndex: 'physical', render: (v) => fmt(v) },
              { title: '混合预测', dataIndex: 'hybrid', render: (v) => fmt(v) },
              { title: '采用值', dataIndex: 'final', render: (v) => fmt(v) },
            ]}
          />
        </Card>
      </div>
    </div>
  );
}

function ModelInfoPanel({ status }) {
  return (
    <div className="model-info-layout">
      <Card className="research-panel" title="模型链路">
        <div className="research-chain-large">
          <div><ExperimentOutlined /> 历史/模拟工况数据</div><span>→</span>
          <div><FundProjectionScreenOutlined /> Attention-LSTM 正向代理</div><span>→</span>
          <div><AimOutlined /> PSO 参数反演与方案搜索</div><span>→</span>
          <div><AreaChartOutlined /> 产能演化预测与方案校核</div>
        </div>
      </Card>

      <Card className="research-panel" title="方案参数范围">
        <Table
          pagination={false}
          size="small"
          dataSource={(status?.inputParameters || []).map((x, i) => ({ ...x, key: i }))}
          columns={[
            { title: '参数', dataIndex: 'name' },
            { title: '下限', render: (_, r) => r.range?.[0] },
            { title: '上限', render: (_, r) => r.range?.[1] },
            { title: '单位', dataIndex: 'unit' },
          ]}
        />
      </Card>

      <Card className="research-panel" title="模型来源与国自然功能映射">
        <Descriptions column={1} bordered size="small">
          <Descriptions.Item label="正向预测模型">{status?.forwardModel || 'Attention-LSTM'}</Descriptions.Item>
          <Descriptions.Item label="方案搜索">{status?.optimizer || 'PSO'}</Descriptions.Item>
          <Descriptions.Item label="产能预测">{status?.productivityModel || 'Double exponential + BP residual correction'}</Descriptions.Item>
          <Descriptions.Item label="输出状态">五钻孔压力 + 方案参数 + 未来产能</Descriptions.Item>
          <Descriptions.Item label="系统角色">方案筛选、状态预测、参数反演、方案校核；后续可与智能控制模块衔接</Descriptions.Item>
        </Descriptions>
        <div className="source-tags">
          {(status?.sourceAssets || []).map((s) => <Tag key={s} color="blue">{s}</Tag>)}
        </div>
      </Card>
    </div>
  );
}

export default function SchemePrediction() {
  const [status, setStatus] = useState(null);

  useEffect(() => {
    request.get('/scheme/status').then((r) => setStatus(r.data)).catch(() => {});
  }, []);

  return (
    <ConfigProvider theme={{ algorithm: theme.defaultAlgorithm, token: { colorBgBase: '#ffffff', colorPrimary: '#187cac', colorText: '#18364b', colorBorder: '#ccdde7', controlHeight: 28 } }}>
    <div className="scheme-page">
      <div className="scheme-page-head">
        <div>
          <Title level={2} style={{ margin: 0, color: '#102d43' }}>煤系气抽采方案预测与优选</Title>
          <Paragraph style={{ margin: '6px 0 0', color: '#5b7487' }}>
            面向采前—采中—采后全生命周期的“状态预测—参数反演—方案筛选—产能校核”科研工作台
          </Paragraph>
        </div>
        <Space>
          <Tag color="cyan">Attention-LSTM</Tag>
          <Tag color="geekblue">PSO</Tag>
          <Tag color="purple">物理 + 数据残差修正</Tag>
        </Space>
      </div>

      <Tabs
        defaultActiveKey="scheme"
        className="scheme-tabs"
        items={[
          { key: 'scheme', label: '方案参数预测', children: <SchemeInversePanel /> },
          { key: 'productivity', label: '产能演化预测', children: <ProductivityPanel /> },
          { key: 'model', label: '模型与参数说明', children: <ModelInfoPanel status={status} /> },
        ]}
      />
    </div>
    </ConfigProvider>
  );
}
