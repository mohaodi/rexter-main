import React, { useState } from 'react';
import { Layout as AntLayout, Tag } from 'antd';
import { AppstoreOutlined, LineChartOutlined, ExperimentOutlined, DeploymentUnitOutlined, ControlOutlined, RobotOutlined } from '@ant-design/icons';
import '../styles/app.css';
import MineOverview from '../pages/MineOverview';
import Simulation from '../pages/Simulation';
import SchemePrediction from '../pages/SchemePrediction';
import RealtimePlatform from '../pages/RealtimePlatform';
import DecisionCenter from '../pages/DecisionCenter';
import AIDecisionWorkbench from '../pages/AIDecisionWorkbench';

const { Content } = AntLayout;

const NAV_ITEMS = [
  { key: 'mine', icon: <AppstoreOutlined />, label: '矿井全局孪生' },
  { key: 'realtime', icon: <LineChartOutlined />, label: '实时监测与数据库' },
  { key: 'scheme', icon: <DeploymentUnitOutlined />, label: '方案预测模型' },
  { key: 'decision', icon: <ControlOutlined />, label: '调控 · 诊断 · 评判' },
  { key: 'ai', icon: <RobotOutlined />, label: 'AI安全决策工作台' },
  { key: 'simulation', icon: <ExperimentOutlined />, label: '物理仿真中心' },
];

export default function Layout() {
  const [page, setPage] = useState('mine');

  const pages = {
    mine: <MineOverview onOpenPrediction={() => setPage('scheme')} onOpenSimulation={() => setPage('simulation')} />,
    scheme: <SchemePrediction />,
    realtime: <RealtimePlatform />,
    decision: <DecisionCenter />,
    ai: <AIDecisionWorkbench />,
    simulation: <Simulation />,
  };

  return (
    <AntLayout className="app-shell">
      <header className="app-topbar">
        <div className="app-brand">
          <div className="brand-mark"><DeploymentUnitOutlined /></div>
          <div className="brand-copy">
            <strong>CBM Digital Twin</strong>
            <span>煤系气全生命周期智能化系统</span>
          </div>
        </div>
        <nav className="app-top-menu" aria-label="系统功能模块">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.key}
              type="button"
              className={page === item.key ? 'top-menu-item is-active' : 'top-menu-item'}
              aria-current={page === item.key ? 'page' : undefined}
              onClick={() => setPage(item.key)}
            >
              {item.icon}<span>{item.label}</span>
            </button>
          ))}
        </nav>
        <div className="topbar-meta">
          <Tag color="gold">仿真数据</Tag>
          <span>V15.10</span>
        </div>
      </header>
      <Content className="app-content">
        {pages[page]}
      </Content>
    </AntLayout>
  );
}
