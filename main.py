"""
书签格式转换器

这个脚本用于在浏览器书签的HTML和JSON格式之间进行转换。
支持单文件转换和批量处理多个文件。

功能:
- HTML转JSON (html2json)
- JSON转HTML (json2html)
- 支持批量处理
- 自动检测书签文件
- 可配置输入/输出路径

使用方法:
    python main.py html2json [-i input.html] [-o output.json]
    python main.py json2html [-i input.json] [-o output.html]
"""

import json
from bs4 import BeautifulSoup
import time
import argparse
import os
import glob
from typing import Dict, List, Optional

# --- HTML 转 JSON 相关函数 ---

def parse_bookmark_folder(dt_element) -> Dict:
    """解析书签文件夹,返回文件夹信息字典"""
    h3_tag = dt_element.find("h3", recursive=False)
    folder = {
        "type": "folder",
        "name": h3_tag.get_text(strip=True),
        "add_date": h3_tag.get("add_date"),
        "last_modified": h3_tag.get("last_modified"),
        "children": []
    }
    
    # 添加工具栏文件夹标记(如果存在)
    if h3_tag.has_attr("personal_toolbar_folder"):
        folder["personal_toolbar_folder"] = h3_tag["personal_toolbar_folder"]
    
    # 处理子元素
    nested_dl = dt_element.find_next_sibling("dl")
    if nested_dl:
        folder["children"] = parse_bookmark_list(nested_dl)
        
    return folder

def parse_bookmark_link(dt_element) -> Dict:
    """解析书签链接,返回链接信息字典"""
    a_tag = dt_element.find("a", recursive=False)
    return {
        "type": "bookmark",
        "name": a_tag.get_text(strip=True),
        "href": a_tag.get("href"),
        "add_date": a_tag.get("add_date"),
        "icon": a_tag.get("icon")
    }

def parse_bookmark_list(dl_element) -> List:
    """解析书签列表,返回书签项目列表"""
    items = []
    if not dl_element:
        return items
        
    for dt_child in dl_element.find_all("dt", recursive=False):
        # 判断是文件夹还是链接
        if dt_child.find("h3", recursive=False):
            item = parse_bookmark_folder(dt_child)
        elif dt_child.find("a", recursive=False):
            item = parse_bookmark_link(dt_child)
        else:
            continue
            
        items.append(item)
    return items

def html_to_json(html_content: str) -> str:
    """将HTML书签内容转换为JSON字符串"""
    soup = BeautifulSoup(html_content, "lxml")
    
    # 查找根书签列表
    root_dl = None
    h1 = soup.find("h1")
    if h1:
        root_dl = h1.find_next_sibling("dl")
    if not root_dl:
        root_dl = soup.find("dl")
    if not root_dl:
        return json.dumps({"error": "找不到主书签列表(DL标签)。"}, indent=4)

    # 解析并转换为JSON
    bookmarks = parse_bookmark_list(root_dl)
    return json.dumps(bookmarks, indent=4, ensure_ascii=False)

# --- JSON 转 HTML 相关函数 ---

def build_folder_html(item: Dict, indent_level: int) -> str:
    """构建文件夹的HTML代码"""
    indent = "    " * indent_level
    html = [
        f'{indent}<DT><H3 ADD_DATE="{item.get("add_date", "")}" '
        f'LAST_MODIFIED="{item.get("last_modified", "")}"'
    ]
    
    if "personal_toolbar_folder" in item:
        html.append(f''' PERSONAL_TOOLBAR_FOLDER="{item["personal_toolbar_folder"]}"''')
    
    html.append(f'>{item.get("name", "未命名文件夹")}</H3>')
    
    if item.get("children"):
        html.append(f'\n{indent}<DL><p>')
        for child in item["children"]:
            html.append(build_bookmark_html(child, indent_level + 1))
        html.append(f'{indent}</DL><p>')
        
    return "\n".join(html)

def build_link_html(item: Dict, indent_level: int) -> str:
    """构建链接的HTML代码"""
    indent = "    " * indent_level
    return (
        f'{indent}<DT><A HREF="{item.get("href", "#")}" '
        f'ADD_DATE="{item.get("add_date", "")}" '
        f'ICON="{item.get("icon", "")}">'
        f'{item.get("name", "未命名书签")}</A>'
    )

def build_bookmark_html(item: Dict, indent_level: int) -> str:
    """根据类型构建书签项的HTML代码"""
    if item.get("type") == "folder":
        return build_folder_html(item, indent_level)
    else:  # bookmark
        return build_link_html(item, indent_level)

def json_to_html(json_content: str) -> str:
    """将JSON内容转换回HTML书签格式"""
    try:
        data = json.loads(json_content)
    except json.JSONDecodeError as e:
        return f"错误: JSON格式无效 - {str(e)}"

    # 构建HTML头部
    html_parts = [
        '<!DOCTYPE NETSCAPE-Bookmark-file-1>',
        '<!-- 这是自动生成的文件。请勿编辑！ -->',
        '<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">',
        '<TITLE>书签</TITLE>',
        '<H1>书签</H1>',
        '<DL><p>'
    ]
    
    # 添加书签内容
    for item in data:
        html_parts.append(build_bookmark_html(item, indent_level=1))
    
    # 添加结束标签
    html_parts.append('</DL><p>')
    
    return '\n'.join(html_parts)

# --- 文件处理函数 ---

def process_file(input_path: str, output_path: str, mode: str) -> bool:
    """处理单个文件的转换
    
    Args:
        input_path: 输入文件路径
        output_path: 输出文件路径
        mode: 转换模式 ('html2json' 或 'json2html')
        
    Returns:
        bool: 转换是否成功
    """
    try:
        # 读取输入文件
        with open(input_path, "r", encoding="utf-8") as f:
            content = f.read()

        # 根据模式进行转换
        if mode == "html2json":
            processed_content = html_to_json(content)
            if "error" in processed_content.lower() and len(processed_content) < 100:
                print(f"HTML转JSON转换错误: {processed_content}")
                return False
        else:
            processed_content = json_to_html(content)
            if processed_content.startswith("错误:"):
                print(f"JSON转HTML转换错误: {processed_content}")
                return False

        # 写入输出文件
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(processed_content)
            
        print(f"成功转换并保存到: {output_path}")
        return True
        
    except Exception as e:
        print(f"处理文件时发生错误: {str(e)}")
        return False

def main():
    """主程序入口"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="在HTML和JSON格式之间转换书签文件。")
    parser.add_argument("mode", choices=["html2json", "json2html"], 
                       help="转换模式: html2json 或 json2html")
    parser.add_argument("-i", "--input", help="输入文件路径")
    parser.add_argument("-o", "--output", help="输出文件路径")
    args = parser.parse_args()

    # 确定要处理的文件
    files_to_process = []
    if args.input:
        if not os.path.isfile(args.input):
            print(f"错误: 找不到输入文件 '{args.input}'")
            return
        files_to_process.append(args.input)
    else:
        # 自动查找匹配的文件
        pattern = "*bookmarks*.html" if args.mode == "html2json" else "*bookmarks*.json"
        files_to_process = glob.glob(pattern)
        if not files_to_process:
            print(f"当前目录下没有找到匹配的文件: '{pattern}'")
            return
        print(f"找到 {len(files_to_process)} 个文件需要处理")

    # 处理每个文件
    for input_file in files_to_process:
        # 确定输出文件路径
        if args.output and len(files_to_process) == 1:
            output_file = args.output
        else:
            base, _ = os.path.splitext(input_file)
            output_file = f"{base}.{'json' if args.mode == 'html2json' else 'html'}"
        
        print(f"\n处理文件: {input_file}")
        process_file(input_file, output_file, args.mode)

    print("\n所有任务完成")

if __name__ == "__main__":
    main()
