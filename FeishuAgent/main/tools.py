import os
import requests
import json
from langchain.tools import tool
from my_utils import *
import pdfplumber # 替换掉 PyPDF2
import requests
import io # 核心：用于处理内存中的二进制流
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.tools import tool
from io import BytesIO
import time

# --- 工具 1: PDF 内容提取 ---

@tool
def read_resume_pdf(file_key: str, message_id: str) -> str:
    """
    【工具】直接读取飞书群聊中的PDF简历内容。
    不需要保存到本地磁盘，直接在内存中处理。
    
    参数:
    - file_key: 飞书消息中的文件唯一标识
    - message_id: 消息ID，用于获取下载权限（必须）
    """
    FEISHU_BASE = os.getenv("FEISHU_BASE")
    APP_ID = os.getenv("APP_ID")
    APP_SECRET = os.getenv("APP_SECRET")
    # print(f"准备读取飞书文件，file_key: {file_key}, message_id: {message_id}")
    try:
        # 1. 获取 Tenant Access Token
        token = get_tenant_token(FEISHU_BASE, APP_ID, APP_SECRET)
        print(f"读取文件正在获取 Token: {token}")
        if not token:
            return "❌ 错误：无法获取飞书访问令牌"
        # https://open.feishu.cn/open-apis/im/v1/messages/:message_id/resources/:file_key
        url = f"{FEISHU_BASE}/im/v1/messages/{message_id}/resources/{file_key}"
        
        headers = {
            "Authorization": f"Bearer {token}"
        }
        params = {
            "type": "file"
        }

        # 4. 发起请求
        response = requests.get(url, headers=headers, params=params)
        # response = requests.get(url, headers=headers)
        # print(f"下载文件响应状态: {response.status_code}")
        if response.status_code != 200:
            return f"❌ 下载失败：HTTP {response.status_code}, {response.text}"
        # print(response.headers)
        # 4. 使用 BytesIO 将二进制数据转换为“文件对象”
        # 这一步实现了“不落地”读取
        file_stream = BytesIO(response.content)
        text_content = ""
        
        with pdfplumber.open(file_stream) as pdf:
            for i, page in enumerate(pdf.pages):
                # extract_text 会自动处理简单的排版
                # 如果有表格，可以用 page.extract_table()
                page_text = page.extract_text()
                if page_text:
                    text_content += f"\n--- 第 {i+1} 页 ---\n{page_text}\n"
        
        # 2. 针对简历的特殊处理
        # 如果简历很短（比如只有一页），直接返回全文
        if len(pdf.pages) == 1:
             return f"简历全文内容：\n{text_content}"
        
        # print("提取到的文本内容:", text_content)
        return text_content

    except Exception as e:
        return f"❌ 处理过程中发生错误: {str(e)}"

@tool
def add_record(fields_data: dict) -> str:
    """
    向飞书多维表格添加一条记录。
    :param fields_data: 包含字段名和值的字典，例如 {"姓名": "张三", "邮箱": "a@b.com"}
    """
    FEISHU_BASE = os.getenv("FEISHU_BASE", "https://open.feishu.cn")
    APP_ID = os.getenv("APP_ID")
    APP_SECRET = os.getenv("APP_SECRET")
    
    # ⚠️ 关键修正：确保这里获取的是正确的环境变量
    # 多维表格的 App Token (通常在 URL 的 /base/xxxx 后面)
    APP_TOKEN = os.getenv("User_Table_Token") 
    # 多维表格的 Table ID (通常在 URL 的 ?table=xxxx 后面，以 tbl 开头)
    TABLE_ID = os.getenv("USER_TABLE_ID")
    print("测试 add_record 工具，准备发送以下数据：")
    print(fields_data)
    token = get_tenant_token(FEISHU_BASE, APP_ID, APP_SECRET)
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID}/records"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    response = requests.post(url, headers=headers, json=fields_data)
    
    if response.status_code == 200:
        print("✅ 插入成功！技能内容已写入。")
    else:
        print(f"❌ 插入失败: {response.text}")

@tool
def read_job_description() -> str:
    """
    读取飞书外接文档的职位描述文本，并返回内容。
    """
    FEISHU_BASE = os.getenv("FEISHU_BASE")
    APP_ID = os.getenv("APP_ID")
    APP_SECRET = os.getenv("APP_SECRET")
    page_id = os.getenv("JobDescribe_Token")
    token = get_tenant_token(FEISHU_BASE, APP_ID, APP_SECRET)
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8"
    }


    
    node_token = page_id
    
    url = f"{FEISHU_BASE}/wiki/v2/spaces/get_node"
    # https://open.feishu.cn/open-apis/docx/v1/documents/:document_id/raw_content
    params = {
        "token": node_token,
        "obj_type": "wiki" # 或者是 "knowledge" 取决于具体版本，通常 wiki 即可
    }

    # print(f"📄 正在请求接口: {url}")
    response = requests.get(url, headers=headers, params=params)
    result = response.json()
    # print(f"接口返回结果: {result}")
    obj_token = result.get("data", {}).get("node", {}).get("obj_token")
    url = f"{FEISHU_BASE}/docx/v1/documents/{obj_token}/raw_content"
    response = requests.get(url, headers=headers)
    raw_content = response.json()
    # print(f"RAG文档内容: {raw_content}")

    # 检查接口调用是否成功
    if raw_content.get("code") == 0:
        # 1. 提取 content 字段（这是一个包含换行符的长字符串）
        content_str = raw_content.get("data", {}).get("content", "")
        
        # 2. 数据清洗：按换行符分割，并去除每行首尾的空格，过滤掉空行
        lines = content_str.split('\n')
        clean_lines = []
        for line in lines:
            stripped_line = line.strip()
            if stripped_line:  # 只保留非空行
                clean_lines.append(stripped_line)
        
        final_text = "\n".join(clean_lines)
        # print(f"最终提取到的文本内容: {final_text}")
        return final_text
        
    else:
        print(f"❌ 读取文档内容失败: {raw_content}")
        return None
@tool
def get_current_day():
    """获取当前日期"""
    now = time.localtime()
    
    year = now.tm_year   
    month = now.tm_mon   
    day = now.tm_mday    
    print(f"当前日期: {year}年{month}月{day}日")
    return year, month, day

import datetime
@tool
def get_order_time(target_month, target_day, target_hour, target_minute=0):
    """
    根据传入的月、日、时，计算会议的时间戳。
    默认年份为当前年份。
    """
    now = datetime.datetime.now()
    current_year = now.year
    
    try:
        target_time = datetime.datetime(current_year, target_month, target_day, target_hour + 1, target_minute)
    except ValueError:
        return None

    if target_time < now:
        target_time = target_time.replace(year=current_year + 1)

    print(f"计算得到的会议时间: {target_time} (Unix 时间戳: {int(target_time.timestamp())})")
    return int(target_time.timestamp())

import secrets

def generate_meeting_code(length=6):
    """
    生成指定长度的纯数字安全密码
    """
    # secrets.choice 从 '0123456789' 中随机选取字符
    # 这种方法比 random 更安全，防止被预测
    return ''.join(secrets.choice('0123456789') for _ in range(length))

@tool
def order_meeting(order_time):
    """预定飞书会议的工具函数。
    参数: order_time (int): 会议开始时间的时间戳"""
    FEISHU_BASE = os.getenv("FEISHU_BASE")
    APP_ID = os.getenv("APP_ID")
    APP_SECRET = os.getenv("APP_SECRET")
    HR_OpenID = os.getenv("HR_OpenID")
    token = get_tenant_token(FEISHU_BASE, APP_ID, APP_SECRET)

    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8"
    }
    url = f"{FEISHU_BASE}/vc/v1/reserves/apply"

    payload =   {
      "end_time": order_time,
      "owner_id": f"{HR_OpenID}",
      "meeting_settings": {
        "topic": "my meeting",
        "meeting_initial_type": 1,
        "auto_record": True,
        "assign_host_list": [
          {
            "user_type": 1,
            "id": f"{HR_OpenID}"
          }
        ],
        "password": f"{generate_meeting_code()}"
      }
    }
     # 6. 发送 POST 请求
    try:
        response = requests.post(url, headers=headers, json=payload)
        
        # 7. 处理响应结果
        if response.status_code == 200:
            res_json = response.json()
            # 飞书 API 成功时 code 通常为 0
            if res_json.get("code") == 0:
                print("✅ 会议预定成功！")
                # 获取会议链接或 ID (具体字段需参考 API 返回文档)
                data = res_json.get("data", {})
                meeting_id = data.get("reserve").get("id")
                meeting_url = data.get("reserve").get("url")
                print(f"会议 ID: {meeting_id}")
                print(f"会议链接: {meeting_url}")
                return meeting_id, meeting_url
            else:
                print(f"❌ 预定失败 (API报错): {res_json.get('msg')}")
                print(f"错误详情: {res_json}")
                return False
        else:
            print(f"❌ 请求失败 (HTTP错误): {response.status_code}")
            print(response.text)
            return False
            
    except Exception as e:
        print(f"❌ 发生异常: {str(e)}")
        return False
def insert_record_to_table(Table_ID: str, Table_TOKEN: str, fields_data: dict) -> str:
    """向飞书多维表格添加一条记录的工具函数。"""
    FEISHU_BASE = os.getenv("FEISHU_BASE", "")
    APP_ID = os.getenv("APP_ID")
    APP_SECRET = os.getenv("APP_SECRET")
    token = get_tenant_token(FEISHU_BASE, APP_ID, APP_SECRET)
    url = f"{FEISHU_BASE}/bitable/v1/apps/{Table_TOKEN}/tables/{Table_ID}/records"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    response = requests.post(url, headers=headers, json=fields_data)
    
    if response.status_code == 200:
        print("✅ 插入成功！技能内容已写入。")
        return "插入成功"
    else:
        print(f"❌ 插入失败: {response.text}")
        return f"插入失败: {response.text}"
    
def get_env(env_name: str) -> str:
    """获取环境变量"""
    return os.getenv(env_name)
@tool
def read_table_record(Table_TOKEN, Table_ID):    
    """读取多维表格记录"""
    FEISHU_BASE = os.getenv("FEISHU_BASE")
    APP_ID = os.getenv("APP_ID")
    APP_SECRET = os.getenv("APP_SECRET")
    token = get_tenant_token(FEISHU_BASE, APP_ID, APP_SECRET)
    Table_TOKEN = os.getenv("Meeting_Table_Token")
    Table_ID = os.getenv("Meeting_Table_ID")
    # 路径结构：/apps/{app_token}/tables/{table_id}/records
    print(f"正在读取表格记录，使用 Table_TOKEN: {Table_TOKEN} 和 Table_ID: {Table_ID}")
    url = f"{FEISHU_BASE}/bitable/v1/apps/{Table_TOKEN}/tables/{Table_ID}/records"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        # 飞书 API 成功时 code 通常为 0
        if data.get('code') == 0:
            items = data.get('data', {}).get('items', [])
            print(items)
            return items # 直接返回记录列表，方便后续处理
        else:
            print(f"❌ API 业务错误: {data}")
            return None
    else:
        print(f"❌ HTTP 请求失败: {response.status_code} - {response.text}")
        return None

    
# read_job_description()
def test():

    set_env()
    FEISHU_BASE = os.getenv("FEISHU_BASE", "https://open.feishu.cn")
    APP_ID = os.getenv("APP_ID")
    APP_SECRET = os.getenv("APP_SECRET")
    
    # ⚠️ 关键修正：确保这里获取的是正确的环境变量
    # 多维表格的 App Token (通常在 URL 的 /base/xxxx 后面)
    APP_TOKEN = os.getenv("User_Table_Token") 
    # 多维表格的 Table ID (通常在 URL 的 ?table=xxxx 后面，以 tbl 开头)
    TABLE_ID = os.getenv("USER_TABLE_ID")
    print("测试 add_record 工具，准备发送以下数据：")
    token = get_tenant_token(FEISHU_BASE, APP_ID, APP_SECRET)
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID}/records"
     
    # 构建请求体
    payload = {
        "fields": {'姓名': '陈宇阳', '邮箱': '768725481@qq.com', 
              '应聘职位': '大模型应用', '教育信息': '硕士 - 广州大学 (软件工程)\n本科 - 三江学院 (软件工程)', 
              '工作/项目经历': '1. FirewaLLM - 隐私保护防火墙 (获华秦杯华为二等奖)\n2. 基于飞书的智能办公助手 - ReAct范式多工具协同Agent系统', 
              '专业技能': 'PyTorch, LangChain, Transformer, RAG, 大模型微调, BERT, NER, 隐私计算'}
    }
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code == 200:
        print("✅ 插入成功！技能内容已写入。")
    else:
        print(f"❌ 插入失败: {response.text}")
# test()
