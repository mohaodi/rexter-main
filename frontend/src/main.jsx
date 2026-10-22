import React from 'react';
import { createRoot } from 'react-dom/client';
import { App, ConfigProvider, theme } from 'antd';
import Layout from './layout/Layout';

createRoot(document.getElementById('root')).render(
  <ConfigProvider
    theme={{
      algorithm: theme.darkAlgorithm,
      token: {
        colorPrimary: '#269bd6',
        borderRadius: 8,
        colorBgBase: '#061522',
        fontSize: 13,
        fontFamily: '"Microsoft YaHei", "PingFang SC", system-ui, sans-serif',
      },
    }}
  >
    <App>
      <Layout />
    </App>
  </ConfigProvider>,
);
