# CBM-DigitalTwin-V14-NSFC

煤系气全生命周期高效抽采智能化系统 V14。该版本按基金项目书“内容四”的同步数字孪生与智能化系统要求，在原 V13 上形成可运行的演示闭环。

## 已实现模块

1. 矿井全局三维孪生。
2. 模拟实时监测和数据库持久化。
3. EA-LSTM + PSO 状态反演与工程方案生成。
4. 钻孔数量、倾角、方位角、间距、长度和负压方案。
5. 分层储层、工作巷和钻孔轨迹三维展示。
6. 双指数物理模型 + BP 残差修正产能预测。
7. 多钻孔协同调控建议。
8. 故障诊断、报警和抽采达标自动评判。
9. COMSOL Java 模型解析和无 COMSOL 在线依赖的降阶仿真。
10. 采前、采中、采后全生命周期状态。

详细设计与依据：

- `SYSTEM_MODULES.md`
- `WORK_MAPPING_20260913.md`
- `TOPIC4_PPT_MAPPING.md`

## 环境

- Python 3.10 或 3.11（3.12 也可运行）
- Node.js 20.x 或 22.x
- npm 10.x

## 最快启动（Windows）

分别双击：

```text
start_backend.bat
start_frontend.bat
```

或使用 PowerShell：

```powershell
cd backend
conda activate cbm_twin
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

另开终端：

```powershell
cd frontend
conda activate cbm_twin
npm install
npm run dev
```

访问：

- 前端：`http://localhost:5173`
- 后端：`http://127.0.0.1:8000`
- 接口文档：`http://127.0.0.1:8000/docs`

## 数据库

默认使用 SQLite，首次启动后端会自动建表，示例数据库位于 `data/cbm_twin.db`。无需先安装数据库服务。

如需生成更多模拟历史数据：

```powershell
python scripts/seed_demo_data.py --points 144 --stage 采中
```

切换 MySQL：

1. 执行 `database/cbm_v14_mysql.sql`。
2. 将 `backend/.env.example` 复制为 `backend/.env`。
3. 设置 `CBM_DB_ENGINE=mysql` 和数据库账号密码。
4. 重启后端。

## 模型说明

用户数据包中的最终模型是增强型 Attention-LSTM，不是 Transformer。Transformer 是汇报中参与对比的模型之一。系统保留 EA-LSTM 权重推理和 PSO 反演，并增加工程约束层生成可视化钻孔方案。

当前三维倾角、间距和轨迹来自工程约束层，不是 EA-LSTM 原始输出。候选方案需结合正式 COMSOL 工况、矿区地质数据和安全规程复核。

## 模拟数据边界

当前未连接矿区，实时页生成的数据全部带有 `sourceType=simulator` 标记。它用于联调数据库、监测、报警、诊断、评判和调控链路，不应作为真实生产数据。接入现场时，用 OPC UA、Modbus TCP、MQTT 或矿区 API 适配器替换 `backend/app/service/realtime_service.py` 中的数据生成入口。

## 自检

```powershell
python scripts/smoke_test.py
cd frontend
npm run build
```
