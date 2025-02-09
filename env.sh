# gpt 配置
if [[ -z "$GPT_PATH" ]]; then
    # 获取当前脚本所在目录
    export GPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi
export GPT_DOC="$GPT_PATH/obsidian"
export PATH="$GPT_PATH/bin:$PATH"
export GPT_PROMPTS_DIR="$GPT_PATH/prompts"
export GPT_LOGS_DIR="$GPT_PATH/logs"

DEBUG=$GPT_DEBUG

# 初始化目录
mkdir -p "$GPT_PATH"/{bin,prompts,logs} 2>/dev/null

function listgpt() {
    local config_file="${1:-$GPT_PATH/model.json}"

    # 检查配置文件是否存在
    [[ -f "$config_file" ]] || {
        echo >&2 "错误：未找到配置文件: $config_file"
        return 1
    }

    # 使用python3解析并列出所有非空key的模型
    python3 -c "import json, sys; config=json.load(open('$config_file')); [print(f'{k}: {v[\"model_name\"]}') for k, v in config.items() if v.get('key')]" 2>/dev/null
}


function usegpt() {
    local model_name="$1"
    local config_file="${2:-$GPT_PATH/model.json}"
    local no_verbose="$3"

    # 检查参数
    [[ -z "$model_name" ]] && {
        echo >&2 "错误：模型名称不能为空"
        return 1
    }

    # 检查配置文件是否存在
    [[ -f "$config_file" ]] || {
        echo >&2 "错误：未找到配置文件: $config_file"
        return 1
    }

    # 使用python3一次性解析并提取所有配置项
    local key base_url model
    read key base_url model <<< $(python3 -c "import json, sys; config=json.load(open('$config_file')).get('$model_name', {}); print(config.get('key', ''), config.get('base_url', ''), config.get('model_name', ''))" 2>/dev/null)

    # 检查是否成功获取配置
    if [[ -z "$key" || -z "$base_url" || -z "$model" ]]; then
        echo >&2 "错误：未找到模型 '$model_name' 或配置不完整"
        return 1
    fi

    # 设置环境变量
    export GPT_KEY="$key"
    export GPT_BASE_URL="$base_url"
    export GPT_MODEL="$model"

    # 如果VERBOSE参数不存在，则输出成功日志
    if [[ -z "$no_verbose" ]]; then
        echo "成功设置GPT环境变量："
        echo "  GPT_KEY: ${key:0:4}****"
        echo "  GPT_BASE_URL: $base_url"
        echo "  GPT_MODEL: $model"
    fi
}

# 检查GPT_PATH和GPT_KEY是否配置
if [[ -z "$GPT_KEY" || -z "$GPT_BASE_URL"  || -z "$GPT_MODEL" ]]; then
    [[ $DEBUG -eq 1 ]] && echo "Debug: 检测到GPT环境变量未配置，尝试使用默认provider" >&2
    
    if [[ -f "$GPT_PATH/model.json" ]]; then
        [[ $DEBUG -eq 1 ]] && echo "Debug: 找到model.json文件: $GPT_PATH/model.json" >&2
        
        # 使用默认的provider
        default_provider=$(python3 -c "import json; config=json.load(open('$GPT_PATH/model.json')); print('default' if 'default' in config else next(iter(config.keys())))" 2>/dev/null)
        
        if [[ -z "$default_provider" ]]; then
            echo >&2 "错误：未设置默认的provider，请在model.json中配置'default'字段"
            [[ $DEBUG -eq 1 ]] && echo "Debug: model.json中未找到default字段，且无法获取第一个provider" >&2
            return 1
        fi
        
        [[ $DEBUG -eq 1 ]] && echo "Debug: 找到默认provider: $default_provider" >&2
        
        if [[ -n "$default_provider" ]]; then
            [[ $DEBUG -eq 1 ]] && echo "Debug: 正在使用默认provider: $default_provider" >&2
            usegpt "$default_provider" "$GPT_PATH/model.json" 1
            if [[ $? -ne 0 ]]; then
                echo >&2 "错误：使用默认provider $default_provider 失败"
                [[ $DEBUG -eq 1 ]] && echo "Debug: usegpt命令执行失败" >&2
                return 1
            fi
        fi
    else
        echo >&2 "错误：未找到model.json文件: $GPT_PATH/model.json"
        [[ $DEBUG -eq 1 ]] && echo "Debug: 在$GPT_PATH路径下未找到model.json文件" >&2
        return 1
    fi
fi


session_id=$(uuidgen)                                                         
export GPT_SESSION_ID=$session_id 

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
                'special:特殊选项:(clipboard tree treefull read)' \
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

    function _usegpt_complete() {
        local config_file="${1:-$GPT_PATH/model.json}"
        
        # 检查配置文件是否存在
        [[ -f "$config_file" ]] || {
            echo >&2 "错误：未找到配置文件: $config_file"
            return 1
        }

        # 获取所有可用的provider名称
        local providers=($(python3 -c "import json, sys; config=json.load(open('$config_file')); [print(k) for k in config.keys() if config[k].get('key')]" 2>/dev/null))

        # 生成补全建议
        _describe 'command' providers
    }

    compdef _usegpt_complete usegpt

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
            special_items=(clipboard tree treefull read)

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

    _usegpt_bash_complete() {
        local cur prev config_file
        cur="${COMP_WORDS[COMP_CWORD]}"
        config_file="${GPT_PATH}/model.json"

        # 检查配置文件是否存在
        if [[ ! -f "$config_file" ]]; then
            echo >&2 "错误：未找到配置文件: $config_file"
            return 1
        fi

        # 获取所有可用的provider名称
        local providers=($(python3 -c "import json, sys; config=json.load(open('$config_file')); [print(k) for k in config.keys() if config[k].get('key')]" 2>/dev/null))

        # 生成补全建议
        COMPREPLY=($(compgen -W "${providers[*]}" -- "$cur"))
    }

    complete -F _usegpt_bash_complete usegpt


fi

