# gpt 配置

# 检查GPT_PATH和GPT_KEY是否配置
if [[ -z "$GPT_PATH" || -z "$GPT_KEY" || -z "$GPT_BASE_URL" ]]; then
    echo >&2 "Error: GPT_PATH, GPT_KEY or GPT_BASE_URL is not configured"
    return 1
fi
export GPT_DOC="$GPT_PATH/logs"
export PATH="$GPT_PATH/bin:$PATH"
export GPT_PROMPTS_DIR="$GPT_PATH/prompts"
export GPT_LOGS_DIR="$GPT_PATH/logs"

# 初始化目录
mkdir -p "$GPT_PATH"/{bin,prompts,logs} 2>/dev/null

# 主函数
function explaingpt() {
    local file="$1"
    local prompt_file="${2:-$GPT_PROMPTS_DIR/source-query.txt}"

    # 参数检查
    [[ -f "$file" ]] || { echo >&2 "Error: Source file not found: $file"; return 1; }
    [[ -f "$prompt_file" ]] || { echo >&2 "Error: Prompt file not found: $prompt_file"; return 1; }

    echo $GPT_PATH/.venv/bin/python $prompt_file $file 
    # 执行核心脚本
    $GPT_PATH/.venv/bin/python $GPT_PATH/llm_query.py --file "$file" --prompt-file "$prompt_file"
}

function askgpt() {
    local question="$@"
    
    # 参数检查
    [[ -z "$question" ]] && { echo >&2 "Error: Question cannot be empty"; return 1; }

    # 执行核心脚本
    $GPT_PATH/.venv/bin/python $GPT_PATH/llm_query.py --ask "$question"
}

_at_complete() {
    # 检查当前输入是否以@开头
    if [[ "$PREFIX" == @* ]]; then
        # 保存原始前缀
        local orig_prefix=$PREFIX
        # 提取@后的部分作为新前缀
        PREFIX=${orig_prefix#@}
        # 设置IPREFIX为@，使得补全结果自动添加@
        IPREFIX="@"

        # 生成补全建议：首先添加clipboard和tree，然后文件补全
        _alternative \
            'special:特殊选项:(clipboard tree, treefull)' \
            'files:文件名:_files'

        # 恢复原始前缀（避免影响其他补全）
        PREFIX=$orig_prefix
        IPREFIX=""
    else
        # 其他情况使用默认文件补全
        _files "$@"
    fi
}

compdef _at_complete askgpt
