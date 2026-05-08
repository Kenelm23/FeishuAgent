import requests
import json
from fastapi import FastAPI, Request

from my_utils import *
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from tools import *
set_env()
APP_ID = os.getenv("APP_ID")
APP_SECRET = os.getenv("APP_SECRET")


app = FastAPI()
user_sessions = {}
processed_messages = set()
FEISHU_BASE = os.getenv("FEISHU_BASE")


def send_reply(open_id, text):
    print(APP_ID, APP_SECRET)
    token = get_tenant_token(FEISHU_BASE, APP_ID, APP_SECRET)
    if not token:
        print("没有 token，无法发送")
        return

    url = f"{FEISHU_BASE}/im/v1/messages?receive_id_type=open_id"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = {
        "receive_id": open_id,
        "content": json.dumps({"text": text}),
        "msg_type": "text"
    }

    try:
        res = requests.post(url, headers=headers, json=data)
        print("发送回复结果:", res.json())
    except Exception as e:
        print("发送失败:", e)

model = ChatOpenAI(
    model="deepseek-chat", 
    api_key=os.getenv("DEEPSEEK_API_KEY"), 
    base_url="https://api.deepseek.com/v1"
)

agent = create_agent(
    model=model, 
    tools=[add_record, read_resume_pdf, read_job_description, order_meeting, get_current_day, get_order_time,
           read_table_record, get_env],
    system_prompt=set_prompt()
)

# 接收飞书消息
@app.api_route("/webhook/feishu", methods=["GET", "POST"])
async def feishu_webhook(request: Request):
    try:
        if request.method == "GET":
            return {"status": "ok"}

        body = await request.body()
        if not body:
            return {"code": 0}

        data = json.loads(body)
        print("📩 飞书数据：", data)

        # 校验 URL
        if "challenge" in data:
            return {"challenge": data["challenge"]}
        
        

        # 处理消息
        event = data.get("event", {})
        message = event.get("message", {})
        sender = event.get("sender", {})
        
        # 3. 关键：获取消息的唯一 ID
        message_id = message.get("message_id")
        
        # 4. 关键：检查是否处理过
        if message_id in processed_messages:
            print(f"⏭️ 消息 {message_id} 已处理过，跳过。")
            return {"code": 0} # 告诉飞书成功了，但不再次处理
        
        # 5. 关键：记录当前消息 ID
        processed_messages.add(message_id)
        # 可选：防止内存泄漏，如果集合太大，可以限制大小
        if len(processed_messages) > 1000:
            processed_messages.pop() 

        if data["header"]["event_type"] == "im.message.receive_v1":
            open_id = sender["sender_id"]["open_id"]

            raw_content = json.loads(message["content"])
            user_text = raw_content.get("text", "")

            print(f"✅ 收到用户 {open_id} 的消息: {user_text}")

            # --- 核心逻辑开始 ---
            
            # 1. 初始化该用户的会话历史 (如果不存在)
            if open_id not in user_sessions:
                user_sessions[open_id] = []

            # 3. 特殊处理：如果是文件消息 (处理简历)
            # 飞书文件消息的 file_key 直接在根节点
            if "file_key" in raw_content:
                file_key = raw_content["file_key"]
                file_name = raw_content.get("file_name", "未知文件")
                message_id = message.get("message_id") 


                print(f"📎 捕获到文件消息: {file_name} (Key: {file_key})")
                
                # 【关键一步】
                # 把文件信息“翻译”成自然语言，骗过 Agent
                # 这样 Agent 就知道该调用 download_feishu_file 工具了
                user_text = f"用户发送了一个文件。请使用file_name: {file_name}, message_id: {message_id}, 和 file_key: {file_key} 进行处理。"
            
            # 2. 处理清空指令
            if user_text.strip().lower() == 'clear' or user_text.strip() == '清除记忆':
                user_sessions[open_id] = [] # 重置列表
                send_reply(open_id, "🧹 记忆已清空，我们可以重新开始聊了！")
                return {"code": 0}

            # 3. 构建发送给 Agent 的消息列表
            # 关键点：这里传入的是【历史记录 + 当前提问】
            messages_for_agent = user_sessions[open_id] + [HumanMessage(content=user_text)]

            # 4. 调用 Agent
            # 注意：这里传入的是完整的消息列表
            response = agent.invoke({"messages": messages_for_agent})
            
            # 5. 获取 AI 回复
            ai_message_content = get_ai_reply(response)
            
            # 6. 更新历史记录 (把刚才的用户提问和 AI 回复都存进去)
            user_sessions[open_id].append(HumanMessage(content=user_text))
            user_sessions[open_id].append(AIMessage(content=ai_message_content))
            print(f"📂 {open_id} 的会话历史：")
            print(user_sessions[open_id])
            print("🤖")
            # 7. 发送回复
            send_reply(open_id, ai_message_content)
            # send_reply(open_id, f"收到啦！你说：{user_text} 😊")

    except Exception as e:
        print("❌ 错误：", e)

    return {"code": 0}


# 启动服务
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)