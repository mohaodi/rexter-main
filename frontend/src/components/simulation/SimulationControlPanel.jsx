import React from 'react';
import { Button, Form, InputNumber, Space, Tag, Popover } from 'antd';

export default function SimulationControlPanel({
  negativePressure,
  setNegativePressure,
  days,
  setDays,
  loading,
  disabled,
  onRun,
  onReset,
}) {
  return (
    <div className="control-panel-content">
      <div className="control-header">
        <div>
          <div className="control-title">参数化仿真</div>
        </div>
        <Tag color="processing">最大 120 d</Tag>
      </div>

      <Form layout="vertical" className="control-form">
        <Form.Item label="抽采负压 / kPa">
          <InputNumber
            min={0}
            max={95}
            precision={2}
            value={negativePressure}
            onChange={(v) => setNegativePressure(v ?? 20)}
            style={{ width: '100%' }}
          />
        </Form.Item>
        <Form.Item label="仿真天数 / d">
          <InputNumber
            min={1}
            max={120}
            value={days}
            onChange={(v) => setDays(v ?? 120)}
            style={{ width: '100%' }}
          />
        </Form.Item>
      </Form>

      <Space wrap className="control-actions">
        <Button type="primary" loading={loading} disabled={disabled} onClick={onRun}>开始仿真</Button>
        <Button onClick={onReset}>恢复默认参数</Button>
        <Popover title="模型计算说明" content={<div style={{ maxWidth: 360 }}>系统基于内置物理模型，保留主要参数、边界函数和传质/达西尺度开展降阶计算。在线结果需通过正式 COMSOL 数值计算校核。</div>}>
          <Button type="text">模型说明</Button>
        </Popover>
      </Space>
    </div>
  );
}
