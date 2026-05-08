import time
import json
import requests
import httpx
import asyncio

# ================= 配置区域 =================
# 飞书应用凭证
APP_ID = "XXX"
APP_SECRET = "XXX"

def test_connection():
    print("1️⃣ 正在获取 Tenant Access Token...")
    
    # 1. 获取 Token
    token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    token_payload = {
        "app_id": APP_ID,
        "app_secret": APP_SECRET
    }
    
    try:
        token_resp = requests.post(token_url, json=token_payload)
        token_data = token_resp.json()
        
        if token_data.get("code") != 0:
            print(f"❌ Token 获取失败: {token_data}")
            return
        
        access_token = token_data.get("tenant_access_token")
        print(f"✅ Token 获取成功: {access_token[:10]}...")

        # 2. 获取当前用户信息
        # 修正 URL：使用 user/me 接口
        print("\n2️⃣ 正在获取机器人自己的信息...")
        # 注意：这里使用的是 /user/me，而不是 /users/me 或 /oauth/...
        user_url = "https://open.feishu.cn/open-apis/user/me"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        user_resp = requests.get(user_url, headers=headers)
        
        # 打印原始内容以便调试
        raw_text = user_resp.text
        # print(f"🔍 原始返回: {raw_text}") # 如果想看详细返回，可以取消注释

        # 检查是否是 JSON
        if not raw_text.strip().startswith("{"):
            print(f"❌ 飞书返回了非 JSON 内容 (可能是 404 页面): {raw_text[:50]}")
            print("💡 提示：请检查上面的 URL 是否正确，或者网络是否有代理干扰。")
            return

        user_data = json.loads(raw_text)
        
        if user_data.get("code") != 0:
            print(f"❌ 获取用户信息失败: {user_data}")
            # 常见错误：99991663 表示缺少 user:me 权限
            return

        # 解析 OpenID
        # user/me 接口的返回结构通常是 data -> user -> open_id
        open_id = user_data.get("data", {}).get("user", {}).get("open_id")
        
        if open_id:
            print(f"✅ 连接成功！")
            print(f"🤖 你的机器人 OpenID 是: {open_id}")
            print("🎉 环境配置正确，可以进行下一步了！")
        else:
            print(f"❌ 解析 OpenID 失败，完整返回数据: {user_data}")

    except Exception as e:
        print(f"❌ 发生网络错误: {e}")

if __name__ == "__main__":
    test_connection()