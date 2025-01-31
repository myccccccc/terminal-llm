# GROQ 配置


# 检查GROQ_PATH和GROQ_KEY是否配置
if [[ -z "$GROQ_PATH" || -z "$GROQ_KEY" ]]; then
    echo >&2 "Error: GROQ_PATH or GROQ_KEY is not configured"
    return 1
fi
export GROQ_DOC="$GROQ_PATH/logs"
export PATH="$GROQ_PATH/bin:$PATH"
export GROQ_PROMPTS_DIR="$GROQ_PATH/prompts"
export GROQ_LOGS_DIR="$GROQ_PATH/logs"

# 初始化目录
mkdir -p "$GROQ_PATH"/{bin,prompts,logs} 2>/dev/null

# 主函数
function explaingroq() {
    local file="$1"
    local prompt_file="${2:-$GROQ_PROMPTS_DIR/source-query.txt}"

    # 参数检查
    [[ -f "$file" ]] || { echo >&2 "Error: Source file not found: $file"; return 1; }
    [[ -f "$prompt_file" ]] || { echo >&2 "Error: Prompt file not found: $prompt_file"; return 1; }

    echo $GROQ_PATH/.venv/bin/python $prompt_file $file 
    # 执行核心脚本
    $GROQ_PATH/.venv/bin/python $GROQ_PATH/groq_query.py --file "$file" --prompt-file "$prompt_file"
}

function askgroq() {
    local question="$@"
    
    # 参数检查
    [[ -z "$question" ]] && { echo >&2 "Error: Question cannot be empty"; return 1; }

    # 执行核心脚本
    $GROQ_PATH/.venv/bin/python $GROQ_PATH/groq_query.py --ask "$question"
}
