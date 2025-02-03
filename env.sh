# gpt 配置

# 检查GPT_PATH和GPT_KEY是否配置
if [[ -z "$GPT_PATH" || -z "$GPT_KEY" || -z "$GPT_BASE_URL"  || -z "GPT_MODEL" ]]; then
    echo >&2 "Error: GPT_PATH, GPT_KEY or GPT_BASE_URL or GPT_MODEL is not configured"
    return 1
fi
export GPT_DOC="$GPT_PATH/obsidian"
export PATH="$GPT_PATH/bin:$PATH"
export GPT_PROMPTS_DIR="$GPT_PATH/prompts"
export GPT_LOGS_DIR="$GPT_PATH/logs"
DEBUG=0
# 初始化目录
mkdir -p "$GPT_PATH"/{bin,prompts,logs} 2>/dev/null

# 主函数
function explaingpt() {
    local file="$1"
    local prompt_file="${2:-$GPT_PROMPTS_DIR/source-query.txt}"

    # 参数检查
    [[ -f "$file" ]] || {
        echo >&2 "Error: Source file not found: $file"
        return 1
    }
    [[ -f "$prompt_file" ]] || {
        echo >&2 "Error: Prompt file not found: $prompt_file"
        return 1
    }

    echo $GPT_PATH/.venv/bin/python $prompt_file $file
    # 执行核心脚本
    $GPT_PATH/.venv/bin/python $GPT_PATH/llm_query.py --file "$file" --prompt-file "$prompt_file"
}

function askgpt() {
    local question="$@"

    # 参数检查
    [[ -z "$question" ]] && {
        echo >&2 "Error: Question cannot be empty"
        return 1
    }

    # 执行核心脚本
    $GPT_PATH/.venv/bin/python $GPT_PATH/llm_query.py --ask "$question"
}

if [[ -n "$ZSH_VERSION" ]]; then
    _at_complete() {
        # 定义调试开关
        local DEBUG=${GPT_DEBUG:-0}

        # 输出调试信息
        [[ $DEBUG -eq 1 ]] && echo "Debug: 当前PREFIX = $PREFIX" >&2
        [[ $DEBUG -eq 1 ]] && echo "Debug: 当前GPT_PATH = $GPT_PATH" >&2

        # 检查当前输入是否以@开头
        if [[ "$PREFIX" == @* ]]; then
            # 保存原始前缀
            local orig_prefix=$PREFIX
            [[ $DEBUG -eq 1 ]] && echo "Debug: 检测到@前缀，原始前缀 = $orig_prefix" >&2

            # 提取@后的部分作为新前缀
            PREFIX=${orig_prefix#@}
            [[ $DEBUG -eq 1 ]] && echo "Debug: 新PREFIX = $PREFIX" >&2

            # 设置IPREFIX为@，使得补全结果自动添加@
            IPREFIX="@"
            [[ $DEBUG -eq 1 ]] && echo "Debug: 设置IPREFIX = $IPREFIX" >&2

            # 获取prompts目录下的文件列表
            local prompt_files=()
            if [[ -d "$GPT_PATH/prompts" ]]; then
                prompt_files=($(ls "$GPT_PATH/prompts"))
                # 只输出一次提示词文件信息
                [[ $DEBUG -eq 1 ]] && echo "Debug: 找到提示词文件: ${prompt_files[@]}" >&2
            else
                [[ $DEBUG -eq 1 ]] && echo "Debug: 未找到提示词目录 $GPT_PATH/prompts" >&2
            fi

            # 生成补全建议：首先添加clipboard和tree，然后prompts目录文件，最后普通文件补全
            [[ $DEBUG -eq 1 ]] && echo "Debug: 开始生成补全建议" >&2
            _alternative \
                'special:特殊选项:(clipboard tree treefull)' \
                'prompts:提示词文件:(${prompt_files[@]})' \
                'files:文件名:_files'

            # 恢复原始前缀（避免影响其他补全）
            PREFIX=$orig_prefix
            IPREFIX=""
            [[ $DEBUG -eq 1 ]] && echo "Debug: 恢复原始前缀 PREFIX = $PREFIX, IPREFIX = $IPREFIX" >&2
        else
            # 其他情况使用默认文件补全
            [[ $DEBUG -eq 1 ]] && echo "Debug: 未检测到@前缀，使用默认文件补全" >&2
            _files "$@"
        fi
    }

    compdef _at_complete askgpt

fi

if [[ -n "$BASH_VERSION" ]]; then
    _askgpt_bash_complete() {
        local cur prev prompt_files special_items
        cur="${COMP_WORDS[COMP_CWORD]}"

        # 处理 @ 开头的补全
        if [[ "$cur" == @* ]]; then
            local prefix="@"
            local search_prefix="${cur#@}"

            # 特殊项
            special_items=(clipboard tree treefull)

            # 提示词文件
            prompt_files=()
            if [[ -d "$GPT_PATH/prompts" ]]; then
                prompt_files=($(ls "$GPT_PATH/prompts" 2>/dev/null))
            fi

            # 生成补全建议
            COMPREPLY=()

            # 特殊项补全
            if [[ -z "$search_prefix" || " ${special_items[@]} " =~ "$search_prefix"* ]]; then
                COMPREPLY+=("${special_items[@]/#/$prefix}")
            fi

            # 提示词文件补全
            if [[ ${#prompt_files[@]} -gt 0 ]]; then
                COMPREPLY+=("${prompt_files[@]/#/$prefix}")
            fi

            # 文件系统补全
            COMPREPLY+=($(compgen -f -- "$search_prefix" | sed 's/^/@/'))
            [[ $DEBUG -eq 1 ]] && echo "Debug: COMPREPLY = ${COMPREPLY[*]}" >&2
            # 过滤匹配项
            COMPREPLY=($(compgen -W "${COMPREPLY[*]}" -- "$cur"))
        else
            # 普通文件补全
            COMPREPLY=($(compgen -f -- "$cur"))
        fi
    }

    complete -F _askgpt_bash_complete askgpt
fi
