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
        default=16000,
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

    for protocol, vars in proxy_vars:
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
    """将代码内容分割成指定大小的块"""
    return [content[i:i+chunk_size] for i in range(0, len(content), chunk_size)]


def query_groq_api(api_key, prompt, proxies=None):
    """向Groq API发送流式查询请求"""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    payload = {
        "messages": [{
            "role": "user",
            "content": prompt
        }],
        "model": "deepseek-r1-distill-llama-70b",
        "temperature": 0.1,
        "max_tokens": 4096,
        "top_p": 0.95,
        "stream": True
    }

    if any(url.startswith('socks') for url in (proxies or {}).values()):
        try:
            import socks
        except ImportError:
            print("错误：使用 SOCKS 代理需要安装 PySocks")
            print("请执行：pip install pysocks")
            sys.exit(1)

    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
            proxies=proxies or None,
            stream=True
        )
        response.raise_for_status()

        content = ""
        for chunk in response.iter_lines():
            if chunk:
                decoded_chunk = chunk.decode('utf-8')
                if decoded_chunk.startswith("data:"):
                    try:
                        chunk_data = json.loads(decoded_chunk[5:])
                        if "choices" in chunk_data and chunk_data["choices"]:
                            delta = chunk_data["choices"][0].get("delta", {})
                            if "content" in delta:
                                print(delta["content"], end="", flush=True)
                                content += delta["content"]
                    except json.JSONDecodeError:
                        continue

        print()  # 换行
        return {"choices": [{"message": {"content": content}}]}

    except requests.exceptions.RequestException as e:
        print(f"API请求失败: {e}")
        sys.exit(1)

def check_glow_installed():
    """检查glow是否已安装"""
    try:
        result = subprocess.run(["which", "glow"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode != 0:
            print("错误：glow 未安装")
            print("请访问 https://github.com/charmbracelet/glow 安装glow")
            print("macOS用户可以使用以下命令安装：")
            print("  brew install glow")
            return False
        return True
    except Exception:
        return False

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

    if not check_glow_installed():
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

    if not args.ask:  # 仅在未使用--ask参数时检查文件
        if not os.path.isfile(args.file):
            print(f"错误：源代码文件不存在 {args.file}")
            sys.exit(1)

        if not os.path.isfile(args.prompt_file):
            print(f"错误：提示词文件不存在 {args.prompt_file}")
            sys.exit(1)

    api_key = os.getenv("GROQ_KEY")
    if not api_key:
        print("错误：未设置GROQ_KEY环境变量")
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
        response_data = query_groq_api(api_key, args.ask, proxies)
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
                response_data = query_groq_api(api_key, chunk_prompt, proxies)
                response_pager = f"\n这是回答的第 {i}/{total_chunks} 部分：\n\n"
                responses.append(response_pager+response_data['choices'][0]['message']['content'])
            final_content = "\n\n".join(responses)
            response_data = {'choices': [{'message': {'content': final_content}}]}
        else:
            full_prompt = prompt_template.format(path=args.file, pager="", code=code_content)
            response_data = query_groq_api(api_key, full_prompt, proxies)

        process_response(response_data, args.file)

    except Exception as e:
        print(f"运行时错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
