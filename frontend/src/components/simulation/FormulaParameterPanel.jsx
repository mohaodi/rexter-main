import React, { useMemo } from 'react';
import { Alert, Empty, Table } from 'antd';
import { InlineMath } from 'react-katex';
import 'katex/dist/katex.min.css';
import FormulaCard from './FormulaCard';

function groupBy(items, key = 'category') {
  return (items || []).reduce((acc, item) => {
    const group = item[key] || '其他';
    if (!acc[group]) acc[group] = [];
    acc[group].push(item);
    return acc;
  }, {});
}

export default function FormulaParameterPanel({ definition }) {
  const parameterGroups = useMemo(() => groupBy(definition?.parameters || []), [definition]);
  const formulaGroups = useMemo(() => groupBy(definition?.formulas || []), [definition]);

  if (!definition) {
    return <Empty description="正在加载物理模型" />;
  }

  const g = definition.geometry || {};
  const solver = definition.solver || {};

  const parameterColumns = [
    {
      title: '符号', dataIndex: 'symbol_latex', width: 105,
      render: (v, row) => (
        <div>
          <div className="parameter-symbol"><InlineMath math={v || row.name} /></div>
          <div className="parameter-source-name">{row.name}</div>
        </div>
      ),
    },
    {
      title: '数值 / 定义', dataIndex: 'value_latex', width: 190,
      render: (v, row) => (
        <div className="parameter-value-cell">
          <InlineMath math={v || row.raw_value || ''} />
          <div className="parameter-raw-value">原始：{row.raw_value}</div>
        </div>
      ),
    },
    { title: '物理含义', dataIndex: 'title' },
  ];

  return (
    <div className="research-scroll-panel">
        {(definition.warnings || []).length > 0 && (
          <Alert
            style={{ marginTop: 8 }}
            type="warning"
            showIcon
            message="模型提示"
            description={(definition.warnings || []).join('；')}
          />
        )}

      <section className="research-section">
        <div className="research-section-title">控制方程（人读数学形式）</div>
        <div className="formula-list">
          {(definition.pde_formulas || []).map((item, idx) => (
            <FormulaCard formula={item} kind="pde" key={`${item.name}-${idx}`} />
          ))}
          {(definition.pde_formulas || []).length === 0 && <Empty description="当前模型未提供控制方程" />}
        </div>
      </section>

      <section className="research-section">
        <div className="research-section-title">派生变量、边界与后处理公式</div>
        {Object.entries(formulaGroups).map(([category, items]) => (
          <div className="formula-category-block" key={category}>
            <div className="formula-category-title">{category}</div>
            <div className="formula-list">
              {items.map((item, idx) => (
                <FormulaCard formula={item} key={`${item.name}-${idx}`} />
              ))}
            </div>
          </div>
        ))}
      </section>

      <section className="research-section">
        <div className="research-section-title">模型参数（按物理类别自动整理）</div>
        {Object.entries(parameterGroups).map(([category, items]) => (
          <div className="parameter-category-block" key={category}>
            <div className="formula-category-title">{category}</div>
            <Table
              rowKey={(row) => `${category}-${row.name}`}
              size="small"
              pagination={false}
              columns={parameterColumns}
              dataSource={items}
              scroll={{ x: 600 }}
            />
          </div>
        ))}
      </section>

      <section className="research-section">
        <div className="research-section-title">几何建模参数</div>
        <div className="kv-grid">
          <div><span>物理模型尺寸</span><b>{(g.java_block_size_m || []).join(' × ')} m</b></div>
          <div><span>数字孪生展示体</span><b>{g.display_box_m?.x} × {g.display_box_m?.y} × {g.display_box_m?.z} m</b></div>
          <div><span>钻孔数量</span><b>{g.borehole_count ?? '未识别'}</b></div>
          <div><span>钻孔半径</span><b>{g.borehole_radius_m ?? '—'} m</b></div>
          <div><span>钻孔直径</span><b>{g.borehole_diameter_m ?? '—'} m</b></div>
          <div><span>钻孔长度</span><b>{g.borehole_length_m ?? '—'} m</b></div>
          <div><span>钻孔间距</span><b>{g.borehole_spacing_m ?? '—'} m</b></div>
        </div>
        <div className="position-list">
          {(g.java_positions || []).map((p) => (
            <div key={p.index}>孔 {p.index}: ({p.x}, {p.y}, {p.z}) m</div>
          ))}
        </div>
      </section>

      <section className="research-section">
        <div className="research-section-title">求解器设置（自动读取可识别项）</div>
        <div className="kv-grid compact">
          {Object.entries(solver).map(([k, v]) => (
            <div key={k}><span>{k}</span><b>{v === null ? '未识别' : String(v)}</b></div>
          ))}
        </div>
      </section>
    </div>
  );
}
