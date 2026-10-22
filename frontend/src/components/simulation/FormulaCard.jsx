import React, { useState } from 'react';
import { Button, Collapse, Tag } from 'antd';
import { BlockMath } from 'react-katex';
import 'katex/dist/katex.min.css';

export default function FormulaCard({ formula, kind = 'formula' }) {
  const [showDetails, setShowDetails] = useState(false);

  const isPde = kind === 'pde';
  return (
    <div className={`human-formula-card ${isPde ? 'pde-card' : ''}`}>
      <div className="human-formula-header">
        <div>
          <div className="human-formula-title">{formula.title || formula.name}</div>
          <div className="human-formula-subtitle">
            {formula.category || (isPde ? '控制方程' : '派生关系')}
          </div>
        </div>
        <Tag color={isPde ? 'geekblue' : 'cyan'}>{formula.name || formula.variable}</Tag>
      </div>

      <div className="latex-display-box">
        <BlockMath
          math={formula.latex || formula.formula || ''}
          renderError={() => (
            <pre className="formula-fallback">{formula.raw || formula.formula || '无法转换该表达式'}</pre>
          )}
        />
      </div>

      {(formula.description || formula.note) && (
        <div className="human-formula-description">{formula.description || formula.note}</div>
      )}

      <Button
        type="link"
        size="small"
        className="formula-source-toggle"
        onClick={() => setShowDetails((v) => !v)}
      >
        {showDetails ? '隐藏计算机表达式' : '查看 Java / COMSOL 原始表达式'}
      </Button>

      {showDetails && (
        <div className="formula-source-details">
          {isPde ? (
            <>
              <div><b>源项 f：</b><code>{formula.source_raw || '—'}</code></div>
              <div><b>时间系数 da：</b><code>{formula.da_raw || '—'}</code></div>
              {Array.isArray(formula.flux_raw) && formula.flux_raw.length > 0 && (
                <div>
                  <b>通量 Γ：</b>
                  {formula.flux_raw.map((v, i) => <code key={i} className="block-code">Γ{i + 1} = {v}</code>)}
                </div>
              )}
            </>
          ) : (
            <code className="block-code">{formula.raw || formula.formula || '—'}</code>
          )}
        </div>
      )}
    </div>
  );
}
