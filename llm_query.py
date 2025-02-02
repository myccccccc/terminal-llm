#!/usr/bin/env python
import os
import sys
import requests
import json
import time
import subprocess
import argparse
from urllib.parse import urlparse
from pathlib import Path
import tempfile
import re
from openai import OpenAI
import platform

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='使用Groq API分析源代码',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        '--file',
        help='要分析的源代码文件路径'
    )
    group.add_argument(
        '--ask',
        help='直接提供提示词内容，与--file互斥'
    )
    parser.add_argument(
        '--prompt-file',
        default=os.path.expanduser('~/.llm/source-query.txt'),
        help='提示词模板文件路径（仅在使用--file时有效）'
    )
    parser.add_argument(
        '--chunk-size',
        type=int,
        default=32000,
        help='代码分块大小（字符数，仅在使用--file时有效）'
    )
    return parser.parse_args()

def sanitize_proxy_url(url):
    """隐藏代理地址中的敏感信息"""
    try:
        parsed = urlparse(url)
        if parsed.password:
            netloc = f"{parsed.username}:****@{parsed.hostname}"
            if parsed.port:
                netloc += f":{parsed.port}"
            return parsed._replace(netloc=netloc).geturl()
        return url
    except Exception:
        return url

def detect_proxies():
    """检测并构造代理配置"""
    proxies = {}
    sources = {}
    proxy_vars = [
        ('http', ['http_proxy', 'HTTP_PROXY']),
        ('https', ['https_proxy', 'HTTPS_PROXY']),
        ('all', ['all_proxy', 'ALL_PROXY'])
    ]

    # 修改代理检测顺序，先处理具体协议再处理all_proxy
    for protocol, vars in reversed(proxy_vars):
        for var in vars:
            if var in os.environ and os.environ[var]:
                url = os.environ[var]
                if protocol == 'all':
                    if not proxies.get('http'):
                        proxies['http'] = url
                        sources['http'] = var
                    if not proxies.get('https'):
                        proxies['https'] = url
                        sources['https'] = var
                else:
                    if protocol not in proxies:
                        proxies[protocol] = url
                        sources[protocol] = var
                break
    return proxies, sources


def split_code(content, chunk_size):
    """将代码内容分割成指定大小的块
    注意：当前实现适用于英文字符场景，如需支持多语言建议改用更好的分块算法
    """
    return [content[i:i+chunk_size] for i in range(0, len(content), chunk_size)]


def query_gpt_api(api_key, prompt, model="gpt-4", proxies=None, base_url=None):
    """使用OpenAI API发送流式查询请求

    参数:
        api_key (str): OpenAI API密钥
        prompt (str): 提示词内容
        model (str): 使用的模型，默认为gpt-4
        proxies (dict): 代理配置
        base_url (str): 自定义API基础URL
    """
    # 初始化OpenAI客户端
    client = OpenAI(
        api_key=api_key,
        base_url=base_url  # 添加base_url参数
    )
    try:
        # 创建流式响应
        stream = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=20480,
            top_p=1,
            stream=True
        )

        content = ""
        # 处理流式响应
        for chunk in stream:
            if chunk.choices[0].delta.content:
                print(chunk.choices[0].delta.content, end="", flush=True)
                content += chunk.choices[0].delta.content

        print()  # 换行
        return {"choices": [{"message": {"content": content}}]}

    except Exception as e:
        print(f"OpenAI API请求失败: {e}")
        sys.exit(1)

def _check_tool_installed(tool_name, install_url=None, install_commands=None):
    """检查指定工具是否已安装"""
    result = subprocess.run(["which", tool_name], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        print(f"错误：{tool_name} 未安装")
        if install_url:
            print(f"请访问 {install_url} 安装{tool_name}")
        if install_commands:
            print("请使用以下命令安装：")
            for cmd in install_commands:
                print(f"  {cmd}")
        return False
    return True

def check_deps_installed():
    """检查glow、tree和剪贴板工具是否已安装"""
    all_installed = True
    
    # 检查glow
    if not _check_tool_installed(
        "glow",
        install_url="https://github.com/charmbracelet/glow",
        install_commands=["brew install glow"]
    ):
        all_installed = False

    # 检查tree
    if not _check_tool_installed(
        "tree",
        install_commands=[
            "macOS: brew install tree",
            "Ubuntu/Debian: sudo apt install tree",
            "CentOS/Fedora: sudo yum install tree"
        ]
    ):
        all_installed = False

    # 检查剪贴板工具
    if sys.platform == 'win32':
        try:
            import win32clipboard
        except ImportError:
            print("错误：需要安装pywin32来访问Windows剪贴板")
            print("请执行：pip install pywin32")
            all_installed = False
    elif sys.platform != 'darwin':  # Linux系统
        clipboard_installed = _check_tool_installed(
            "xclip",
            install_commands=[
                "Ubuntu/Debian: sudo apt install xclip",
                "CentOS/Fedora: sudo yum install xclip"
            ]
        ) or _check_tool_installed(
            "xsel",
            install_commands=[
                "Ubuntu/Debian: sudo apt install xsel",
                "CentOS/Fedora: sudo yum install xsel"
            ]
        )
        if not clipboard_installed:
            all_installed = False

    return all_installed


def get_directory_context(max_depth=1):
    """获取当前目录上下文信息（支持动态层级控制）"""
    try:
        current_dir = os.getcwd()
        cmd = ["tree"]
        if max_depth is not None:
            cmd.extend(["-L", str(max_depth)])

        result = subprocess.run(cmd, 
                              stdout=subprocess.PIPE, 
                              stderr=subprocess.PIPE, 
                              text=True)

        if result.returncode == 0:
            output = result.stdout
            # 仅在无层级限制时检查输出长度
            if max_depth is None and len(output.encode()) > 2048:
                return get_directory_context(max_depth=1)  # 递归调用回退到一层
            return f"\n当前工作目录: {current_dir}\n\n目录结构:\n{output}"

        # 当tree命令失败时使用ls
        ls_result = subprocess.run(["ls", "-l"],
                                 stdout=subprocess.PIPE,
                                 text=True)
        msg = ls_result.stdout or '无法获取目录信息'
        return f"\n当前工作目录: {current_dir}\n\n目录结构:\n{msg}"

    except Exception as e:
        return f"获取目录上下文时出错: {str(e)}"

def process_text_with_tree(text):
    """处理包含@tree的文本，获取目录上下文并附加"""
    if "@tree" in text:
        # 移除@tree标记
        text = text.replace("@tree", "")
        # 获取目录上下文
        dir_context = get_directory_context()
        # 将目录上下文附加到文本后
        text = f"{text}\n{dir_context}"
    return text


def get_clipboard_content():
    """获取系统剪贴板内容，支持Linux、Mac、Windows"""
    try:
        # 判断操作系统
        if sys.platform == 'win32':
            # Windows系统
            import win32clipboard
            win32clipboard.OpenClipboard()
            data = win32clipboard.GetClipboardData()
            win32clipboard.CloseClipboard()
            return data
        elif sys.platform == 'darwin':
            # Mac系统
            process = subprocess.Popen(['pbpaste'], stdout=subprocess.PIPE)
            stdout, _ = process.communicate()
            return stdout.decode('utf-8')
        else:
            # Linux系统
            # 尝试xclip
            try:
                process = subprocess.Popen(['xclip', '-selection', 'clipboard', '-o'],
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                stdout, _ = process.communicate()
                if process.returncode == 0:
                    return stdout.decode('utf-8')
            except FileNotFoundError:
                pass

            # 尝试xsel
            try:
                process = subprocess.Popen(['xsel', '--clipboard', '--output'],
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                stdout, _ = process.communicate()
                if process.returncode == 0:
                    return stdout.decode('utf-8')
            except FileNotFoundError:
                pass

            return "无法获取剪贴板内容：未找到xclip或xsel"
    except Exception as e:
        return f"获取剪贴板内容时出错: {str(e)}"


def fetch_url_content(url):
    """通过API获取URL对应的Markdown内容"""
    try:
        api_url = f"http://127.0.0.1:8000/convert?url={url}"
        response = requests.get(api_url)
        response.raise_for_status()
        return response.text
    except Exception as e:
        return f"获取URL内容失败: {str(e)}"
    
def process_text_with_file_path(text):
    """处理包含@...的文本，支持@cmd命令、@path文件路径、@http网址和prompts目录下的模板文件"""

    # 定义命令映射表
    cmd_map = {
        'clipboard': get_clipboard_content,
        "tree": get_directory_context,
        'treefull': lambda: get_directory_context(max_depth=None),
    }
    
    # 定义环境变量
    env_vars = {
        'os': sys.platform,
        'os_version': platform.version(),
        'current_path': os.getcwd(),
    }

    # 使用正则表达式查找所有@开头的命令或路径
    matches = re.findall(r'@([^\s]+)', text)

    for match in matches:
        match_key = f"@{match} "
        try:
            # 处理命令
            if match in cmd_map:
                result = cmd_map[match]()
                text = text.replace(match_key, result)
                continue
            
            # 尝试展开相对路径
            expanded_path = os.path.abspath(os.path.expanduser(match))

            # 优先检查prompts目录下的文件
            prompts_path = os.path.join(os.path.dirname(__file__), 'prompts', match)
            if os.path.exists(prompts_path):
                with open(prompts_path, 'r', encoding='utf-8') as f:
                    content = f.read(10240)  # 最多读取10k
                    # 替换模板中的环境变量
                    content = content.format(**env_vars)
                text = text.replace(match_key, f"\n{content}\n")
                continue

            if os.path.exists(expanded_path):
                with open(expanded_path, 'r', encoding='utf-8') as f:
                    content = f.read(10240)  # 最多读取10k
                text = text.replace(match_key, f"\n\n文件 {expanded_path} 内容:\n```\n{content}\n```\n\n")
                continue

            # 处理URL
            if match.startswith('http'):
                markdown_content = fetch_url_content(match)
                text = text.replace(match_key, f"\n\n参考URL: {match} \n内容(已经转换成markdown):\n{markdown_content}\n\n")
                continue

            # 未找到匹配项
            print(f"错误：未找到命令、文件或URL: {match}")
            sys.exit(1)

        except Exception as e:
            print(f"处理 {match} 时出错: {str(e)}")
            sys.exit(1)

    return text

def process_response(response_data, file_path, save=True):
    """处理API响应并保存结果"""
    if not response_data['choices']:
        raise ValueError("API返回空响应")

    content = response_data['choices'][0]['message']['content']

    # 获取文件扩展名
    ext = Path(file_path).suffix[1:] if Path(file_path).suffix else 'txt'

    # 处理文件路径
    file_path = Path(file_path)
    if file_path.is_absolute():
        parts = file_path.parts[-2:]
        relative_path = Path(*parts)
    else:
        relative_path = file_path

    if save:
        # 创建保存目录
        base_dir = Path(os.getenv("GROQ_DOC", os.getcwd()))
        save_dir = base_dir / "groq_responses" / relative_path.parent
        os.makedirs(save_dir, exist_ok=True)

        base_name = os.path.basename(file_path).split(".")[0]
        save_path = save_dir / f"response-{base_name}-{ext}.md"

        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(content)
    else:
        # 使用临时文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', encoding='utf-8', delete=False) as tmp_file:
            tmp_file.write(content)
            save_path = tmp_file.name

    if not check_deps_installed():
        sys.exit(1)

    try:
        subprocess.run(["glow", save_path], check=True)
        # 如果是临时文件，使用后删除
        if not save:
            os.unlink(save_path)
    except subprocess.CalledProcessError as e:
        print(f"glow运行失败: {e}")
        sys.exit(1)

def main():
    args = parse_arguments()

    # 集中检查环境变量
    api_key = os.getenv("GPT_KEY")
    if not api_key:
        print("错误：未设置GPT_KEY环境变量")
        sys.exit(1)

    base_url = os.getenv("GPT_BASE_URL")
    if not base_url:
        print("错误：未设置GPT_BASE_URL环境变量")
        sys.exit(1)
    try:
        parsed_url = urlparse(base_url)
        if not all([parsed_url.scheme, parsed_url.netloc]):
            print(f"错误：GPT_BASE_URL不是有效的URL: {base_url}")
            sys.exit(1)
    except Exception as e:
        print(f"错误：解析GPT_BASE_URL失败: {e}")
        sys.exit(1)

    if not args.ask:  # 仅在未使用--ask参数时检查文件
        if not os.path.isfile(args.file):
            print(f"错误：源代码文件不存在 {args.file}")
            sys.exit(1)

        if not os.path.isfile(args.prompt_file):
            print(f"错误：提示词文件不存在 {args.prompt_file}")
            sys.exit(1)

    proxies, proxy_sources = detect_proxies()
    if proxies:
        print("⚡ 检测到代理配置：")
        max_len = max(len(p) for p in proxies.keys())
        for protocol in sorted(proxies.keys()):
            source_var = proxy_sources.get(protocol, 'unknown')
            sanitized = sanitize_proxy_url(proxies[protocol])
            print(f"  ├─ {protocol.upper().ljust(max_len)} : {sanitized}")
            print(f"  └─ {'via'.ljust(max_len)} : {source_var}")
    else:
        print("ℹ️ 未检测到代理配置")

    if args.ask:
        text = process_text_with_file_path(args.ask)
        print(text)
        response_data = query_gpt_api(api_key, text, proxies=proxies, model=os.environ["GPT_MODEL"], base_url=base_url)
        process_response(response_data, "", save=False)
        return

    try:
        with open(args.prompt_file, 'r', encoding='utf-8') as f:
            prompt_template = f.read().strip()
        with open(args.file, 'r', encoding='utf-8') as f:
            code_content = f.read()

        # 如果代码超过分块大小，则分割处理
        if len(code_content) > args.chunk_size:
            code_chunks = split_code(code_content, args.chunk_size)
            responses = []
            total_chunks = len(code_chunks)
            for i, chunk in enumerate(code_chunks, 1):
                # 在提示词中添加当前分块信息
                pager = f"这是代码的第 {i}/{total_chunks} 部分：\n\n"
                print(pager)
                chunk_prompt = prompt_template.format(path=args.file, pager=pager, code=chunk)
                response_data = query_gpt_api(api_key, chunk_prompt, proxies=proxies, model=os.environ["GPT_MODEL"], base_url=base_url)
                response_pager = f"\n这是回答的第 {i}/{total_chunks} 部分：\n\n"
                responses.append(response_pager+response_data['choices'][0]['message']['content'])
            final_content = "\n\n".join(responses)
            response_data = {'choices': [{'message': {'content': final_content}}]}
        else:
            full_prompt = prompt_template.format(path=args.file, pager="", code=code_content)
            response_data = query_gpt_api(api_key, full_prompt, proxies=proxies, model=os.environ["GPT_MODEL"], base_url=base_url)

        process_response(response_data, args.file)

    except Exception as e:
        print(f"运行时错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
