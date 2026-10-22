import React, { useEffect, useState } from 'react';
import { App, Spin } from 'antd';
import request from '../api/request';
import FormulaParameterPanel from '../components/simulation/FormulaParameterPanel';
import ThreeTwinPanel from '../components/simulation/ThreeTwinPanel';
import SimulationResultPanel from '../components/simulation/SimulationResultPanel';
import SimulationControlPanel from '../components/simulation/SimulationControlPanel';
import '../styles/research-simulation.css';

const DEFAULT_MODEL_ID = 'BigDataFixed_120d_AutoInit';

export default function Simulation() {
  const { message } = App.useApp();
  const [definition, setDefinition] = useState(null);
  const [negativePressure, setNegativePressure] = useState(20);
  const [days, setDays] = useState(120);
  const [simulation, setSimulation] = useState(null);
  const [loadingDefinition, setLoadingDefinition] = useState(true);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    let active = true;
    request.get(`/research/models/${encodeURIComponent(DEFAULT_MODEL_ID)}/definition`)
      .then((res) => { if (active) setDefinition(res.data); })
      .catch((err) => { if (active) message.error(err?.response?.data?.detail || '无法加载内置物理模型'); })
      .finally(() => { if (active) setLoadingDefinition(false); });
    return () => { active = false; };
  }, [message]);

  const runSimulation = async () => {
    setRunning(true);
    try {
      const res = await request.post('/research/simulate', {
        model_id: DEFAULT_MODEL_ID,
        negative_pressure_kpa: negativePressure,
        days,
        mode: 'constant',
      });
      setSimulation(res.data);
      message.success(`已完成 0–${days} d 后端降阶仿真`);
    } catch (err) {
      message.error(err?.response?.data?.detail || '仿真请求失败');
    } finally {
      setRunning(false);
    }
  };

  const reset = () => {
    setNegativePressure(20);
    setDays(120);
    setSimulation(null);
  };

  return (
    <div className="research-simulation-page">
      <div className="research-page-header">
        <div>
          <h1>煤系气抽采物理—数据融合数字孪生仿真中心</h1>
          <p>物理方程与参数 · 三维数字孪生 · 0–120 d 参数化仿真</p>
        </div>
        <div className="header-status">物理 · 数据融合</div>
      </div>

      <div className="research-grid">
        <div className="research-panel formula-panel">
          <div className="panel-title">物理模型、控制方程与参数体系</div>
          <Spin spinning={loadingDefinition} tip="加载物理模型...">
            <FormulaParameterPanel definition={definition} />
          </Spin>
        </div>

        <div className="research-panel twin-panel">
          <div className="panel-title">三维数字孪生模型</div>
          <ThreeTwinPanel definition={definition} />
        </div>

        <div className="research-panel result-panel">
          <div className="panel-title">逐日仿真值与演化曲线</div>
          <SimulationResultPanel simulation={simulation} />
        </div>

        <div className="research-panel control-panel">
          <div className="panel-title">仿真参数与计算控制</div>
          <SimulationControlPanel
            negativePressure={negativePressure}
            setNegativePressure={setNegativePressure}
            days={days}
            setDays={setDays}
            loading={running}
            disabled={loadingDefinition || !definition}
            onRun={runSimulation}
            onReset={reset}
          />
        </div>
      </div>
    </div>
  );
}
