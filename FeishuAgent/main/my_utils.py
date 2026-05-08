import os
import yaml
import requests
def set_env():
    with open("./data/application.yml", "r") as f:
        config = yaml.safe_load(f)
    os.environ["APP_ID"] = config.get("APP_ID", "")
    os.environ["APP_SECRET"] = config.get("APP_SECRET", "")
    os.environ["FEISHU_BASE"] = config.get("FEISHU_BASE", "")
    os.environ["DEEPSEEK_API_KEY"] = config.get("DeepSeek_API_KEY", "")
    os.environ["HR_OpenID"] = config.get("HR_OpenID", "")
    os.environ["User_Table_ID"] = config.get("User_Table_ID", "")
    os.environ["User_Table_Token"] = config.get("User_Table_Token", "")
    os.environ["JobDescribe_Token"] = config.get("JobDescribe_Token", "")
    os.environ["Meeting_Table_Token"] = config.get("Meeting_Table_Token", "")
    os.environ["Meeting_Table_ID"] = config.get("Meeting_Table_ID", "")
def get_tenant_token(FEISHU_BASE, APP_ID, APP_SECRET):
    url = f"{FEISHU_BASE}/auth/v3/tenant_access_token/internal"
    print("get_tenant_token", url)
    resp = requests.post(url, json={"app_id": APP_ID, "app_secret": APP_SECRET}).json()
    return resp["tenant_access_token"]

def set_prompt():
    with open("./data/prompts/prompt.md", "r", encoding="utf-8") as f:
            content = f.read()
            print("✅ 成功加载系统提示词...")
            return content


def get_ai_reply(agent_response: dict) -> str:
    """
    从 agent.invoke 的返回结果中提取最终的 AI 文本回复。
    """
    # 优先检查是否有直接的 'output' 字段
    if 'output' in agent_response:
        return agent_response['output']
    
    # 否则从 messages 列表中提取最后一条 AI 消息
    messages = agent_response.get('messages', [])
    for message in reversed(messages):
        # 检查是否是 AI 消息且包含内容
        if hasattr(message, 'type') and message.type == 'ai':
            if hasattr(message, 'content') and message.content:
                return message.content
    
    return "未能解析到有效回复"