# 开源依赖与设计参考

本项目未整体复制或改名发布任何现成小说问答仓库。业务实现、提示词、测试和原创小说为本次工作编写；通过标准依赖安装复用成熟算法。若提交课程报告，须同时说明这些依赖和本项目自己的进度控制、证据校验与实验工作。

| 项目 | 本项目如何使用 | 上游许可证 |
|---|---|---|
| [rank_bm25](https://github.com/dorianbrown/rank_bm25) | Python 依赖，BM25 评分；中文切词、进度过滤和混合检索由本项目组织 | Apache-2.0 |
| [jieba](https://github.com/fxsjy/jieba) | 中文分词依赖 | MIT |
| [FastAPI](https://github.com/fastapi/fastapi) | HTTP 接口、校验、OpenAPI | MIT |
| [Pydantic](https://github.com/pydantic/pydantic) | 输入和模型输出结构校验 | MIT |
| [HTTPX](https://github.com/encode/httpx) | 可配置模型服务 HTTP 客户端 | BSD-3-Clause |
| [Uvicorn](https://github.com/encode/uvicorn) | ASGI 服务 | BSD-3-Clause |
| [LlamaIndex CitationQueryEngine](https://github.com/run-llama/llama_index/blob/main/llama-index-core/llama_index/core/query_engine/citation_query_engine.py) | 参考编号证据与回答引用的设计；未安装此框架、未复制其提示词或源码 | MIT |
| [Paige book-context.ts](https://github.com/derekmpeterson/paige/blob/main/lib/book-context.ts) | 参考阅读进度裁剪上下文；本项目按章节和段落实现，未复制源码 | MIT |
| [StorySphere](https://github.com/willim9313/storysphere) | 前期调研参考整体小说分析架构；无代码引入 | MIT |

上游许可证以各仓库及已安装发行包自带 LICENSE 为准。`rank_bm25` 的 GitHub LICENSE 已核对为 Apache License 2.0；不要把它误写成 MIT。`requirements.lock.txt` 记录本次验证环境的实际依赖版本。分发第三方源码或打包虚拟环境时应保留对应许可证；通常只提交本项目源码和依赖清单。

## 扩展实验语料及预处理

四部原著为公版作品；实验只使用下列电子版本前五回的处理选段。原始下载及其 Project Gutenberg 声明保留于 `evaluation/corpus_v1/sources/`，传播电子版本时保留相应声明并遵守随文件提供的使用条件。

| 作品 | 来源 | 本项目用途 |
|---|---|---|
| 红楼梦 | https://www.gutenberg.org/ebooks/24264 | 开发集 |
| 三国志演义 | https://www.gutenberg.org/ebooks/23950 | 按书留出集 |
| 水浒传 | https://www.gutenberg.org/ebooks/23863 | 按书留出集 |
| 老残游记 | https://www.gutenberg.org/ebooks/23850 | 按书留出集 |

URL、文件摘要、版本章序与处理方法见 `evaluation/corpus_v1/source_manifest.json`。来源文件夹另有未纳入实验的儒林外史下载文件，不计入本次数据规模。题目及参考 A/B 记录由助手整理，未直接来自第三方问答数据集，仍待人工校验。

语料准备使用 [opencc-python-reimplemented](https://pypi.org/project/opencc-python-reimplemented/) 0.1.7 做繁简转换，安装元数据声明 Apache License，具体许可随发行包。仅为预处理依赖，版本固定在 `evaluation/corpus_v1/requirements-preparation.txt`；读取已冻结语料无需重新安装或处理。
