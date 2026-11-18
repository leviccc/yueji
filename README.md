# 阅迹

阅迹是面向中文小说的阅读辅助工具。它按读者当前的已读章节整理情节时间线、人物关系和证据问答，并支持从分析结果回到对应原文。

## 本地启动

需要 Python 3.11+ 和 Node.js。以下命令在仓库根目录运行，适用于 macOS 或 Linux。

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r integration/requirements.txt
npm --prefix yueji-ui install
npm --prefix yueji-ui run build
.venv/bin/python -m uvicorn integration.app:create_app --factory --host 127.0.0.1 --port 8000
```

打开 [本地工作台](http://127.0.0.1:8000)。默认载入《长安来信》的两个示例版本。可以从 [示例书库](data/测评书库/) 导入三部古典小说的选段，或导入自己的 TXT。无模型密钥时可以阅读、调整进度和检索原文。生成新摘要、人物档案和问答需要配置自己的模型 API，配置说明见[整合文档](integration/README.md)。

## 代码与实验

| 目录 | 内容 |
| --- | --- |
| [a](a/README.md) | 情节提要、事件时序和双结局测试文本 |
| [b](b/README.md) | 人物、别名、关系和原文核验 |
| [c](c/README.md) | 原文检索、引用问答和支持性核验 |
| [integration](integration/README.md) | 统一 API、阅读进度、任务、会话和计量 |
| [yueji-ui](yueji-ui/) | Vue 阅读工作台 |

事件对导出见[时序复现说明](a/docs/TEMPORAL.md)。关系抽取开发集见[《孤独者》评测](b/evaluation_guduzhe.md)。多书问答的语料、配置、指标和留出集结果见[问答实验说明](c/evaluation/README.md)。

课程演示站点及访问方式由项目组单独提供。
