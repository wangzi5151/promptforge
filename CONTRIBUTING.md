# 贡献指南 / Contributing

感谢关注 PromptForge！欢迎一切形式的贡献。

## 快速开始

```bash
git clone https://github.com/wangzi5151/promptforge.git
cd promptforge
pip install -r requirements-dev.txt
make test      # 运行测试
make run       # 启动开发服务器 http://localhost:8000
```

## 贡献流程

1. Fork 仓库并创建特性分支：`git checkout -b feature/amazing`
2. 提交更改，确保 `pytest` 全部通过
3. 推送分支并创建 Pull Request（描述动机与改动）
4. CI（Python 3.10–3.12 + Docker 构建）通过后即可合并

## 规范

- 代码风格遵循 PEP 8，新增功能请附带测试
- 界面改动请保持现有设计语言（玻璃拟态、暗色主题）
- 提交信息使用英文祈使句或中文均可，但要清晰

## 报告 Bug

请到 [Issues](https://github.com/wangzi5151/promptforge/issues) 提交，附上复现步骤与截图。
