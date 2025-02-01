
# terminal LLM

一个基于大模型的智能终端代码分析与问答工具，提供便捷的命令行交互和上下文感知功能。

## 功能特性

- **代码文件分析**：替代view, vim, 用大模型分析本地源代码文件
- **智能问答**：提供自然语言交互的问答功能
- **上下文集成**：
  - 剪贴板内容自动读取 (`@clipboard`)
  - 目录结构查看 (`@tree`/`@treefull`)
  - 文件内容嵌入 (`@文件路径`)
  - 网页内容嵌入 (`@http://example.com`)
  - 常用prompt引用 (`@quicksort`)
- **网页内容转换**：内置Web服务器提供HTML转Markdown服务
  - 浏览器扩展集成支持, 绕过cloudflare干扰
  - 自动内容提取与格式转换
- **智能分块处理**：自动处理大文件分块分析
- **代理支持**：完善的HTTP代理配置检测
- **流式响应**：实时显示API响应内容

**上下文嵌入语法**
```bash
# 分析剪贴板内容
askgpt "解释这段代码：@clipboard"

# 附加当前目录结构
askgpt "@tree，请分析主要模块"

# 附加当前目录结构全部
askgpt "@treefull，请分析主要模块"

# 嵌入文件内容
askgpt "请优化这个配置文件：@config/settings.yaml"

# 访问网页
askgpt @https://tree-sitter.github.io/tree-sitter/using-parsers/1-getting-started.html 归纳这个文档

# 嵌入常用提示词, 文件放到在prompts/目录
askgpt @quicksort
```


## 安装与配置

1. **克隆仓库**
```bash
git clone https://github.com/maliubiao/terminal-llm
cd terminal-llm
```

2. **设置虚拟环境**
```bash
uv sync
source .venv/bin/activate
```

3. **环境变量配置**
```bash
# 在shell配置文件中添加 (~/.bashrc 或 ~/.zshrc)
export GPT_PATH="/path/to/terminal-llm"
export GPT_KEY="your-api-key"
export GPT_MODEL="your-model"
export GPT_BASE_URL="https://api.example.com/v1"  # OpenAI兼容API地址
source $GPT_PATH/env.sh #zsh支持@后补全，bash没测过
```

## 使用指南

### 基本命令

**分析源代码文件**
```bash
explaingpt path/to/file.py
# 使用自定义提示模板
explaingpt file.py prompts/custom-prompt.txt
```

**直接提问**
```bash
askgpt "如何实现快速排序算法？"
```

### 高级功能

**网页内容转换服务**
```bash
# 启动转换服务器（默认端口8000), 用https://github.com/microsoft/markitdown实现
python server/server.py

# 调用转换接口（需配合浏览器扩展使用），server/plugin加载到浏览器
curl "http://localhost:8000/convert?url=当前页面URL"
```


### 提示词模板

在`prompts/`目录中创建自定义模板：
```txt
请分析以下Python代码：
{{代码内容}}

主要任务：
1. 解释核心功能
2. 找出潜在bug
3. 提出优化建议
```

## 环境变量

| 变量名         | 说明                          |
|---------------|-----------------------------|
| `GPT_PATH`    | 项目根目录路径                   |
| `GPT_KEY`     | OpenAI API密钥          |
| `GPT_BASE_URL`| API基础地址 (默认Groq官方端点)   |
| `GPT_KEY`     | API KEY    |

## 目录结构

```
groq/
├── bin/              # 工具脚本
├── server/           # 网页转换服务
│   └── server.py     # 转换服务器主程序
├── prompts/          # 提示词模板
├── logs/             # 运行日志
├── llm_query.py      # 核心处理逻辑
├── tree_search.py    # 目录结构分析
├── env.sh            # 环境配置脚本
└── pyproject.toml    # 项目依赖配置
```


## 注意事项

1. **依赖工具**：
   - 安装[glow](https://github.com/charmbracelet/glow)用于Markdown渲染
   - 安装`tree`命令查看目录结构
   - Windows用户需要安装pywin32

2. **代理配置**：
   自动检测`http_proxy`/`https_proxy`环境变量

3. **文件分块**：
   大文件自动分块处理（默认32k字符/块）

4. **网页转换服务依赖**：
   - 需要安装Chrome浏览器扩展配合使用
   - 确保8000端口未被占用
   - 转换服务仅接受本地连接

## 示例

```bash
# 分析当前目录结构
askgpt "根据当前项目结构@tree，请说明主要模块的作用"

# 优化剪贴板中的代码
askgpt "优化这段代码的性能：@clipboard"

# 结合配置文件分析
explaingpt config.yaml prompts/config-analysis.txt
```

## 许可证

MIT License © 2024 maliubiao


