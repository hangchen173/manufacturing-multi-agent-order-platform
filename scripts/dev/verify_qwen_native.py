#!/usr/bin/env python3
import os
from dotenv import load_dotenv
import time

load_dotenv()

QWEN_PRICING = {
    "qwen-max": {
        "input": 0.02,
        "output": 0.06
    },
    "qwen-plus": {
        "input": 0.004,
        "output": 0.012
    },
    "qwen-vl-plus": {
        "input": 0.008,
        "output": 0.02
    }
}

def test_with_dashscope():
    print("=" * 60)
    print("🤖 使用DashScope原生SDK验证模型")
    print("=" * 60)
    
    try:
        import dashscope
        from dashscope import Generation
    except ImportError:
        print("❌ dashscope库未安装")
        print("正在安装 dashscope...")
        import subprocess
        subprocess.check_call([".venv/bin/pip", "install", "dashscope"])
        import dashscope
        from dashscope import Generation
    
    api_key = os.getenv("QWEN_API_KEY")
    if not api_key:
        print("❌ 未设置QWEN_API_KEY")
        return
    
    dashscope.api_key = api_key
    
    models = ["qwen-max", "qwen-plus", "qwen-vl-plus"]
    test_message = "你好，请用一句话介绍你自己"
    
    total_cost = 0
    total_input_tokens = 0
    total_output_tokens = 0
    
    for model in models:
        print(f"\n🔍 测试模型: {model}")
        print("-" * 60)
        
        try:
            response = Generation.call(
                model=model,
                prompt=test_message,
                max_tokens=100,
                temperature=0
            )
            
            if response.status_code == 200:
                print(f"✅ 模型调用成功！")
                print(f"📤 输入: {test_message}")
                print(f"📥 输出: {response.output.text}")
                
                if hasattr(response, 'usage'):
                    input_tokens = response.usage.input_tokens
                    output_tokens = response.usage.output_tokens
                    total_tokens = response.usage.total_tokens
                    
                    print(f"\n📊 Token统计:")
                    print(f"   输入Token: {input_tokens}")
                    print(f"   输出Token: {output_tokens}")
                    print(f"   总计Token: {total_tokens}")
                    
                    pricing = QWEN_PRICING.get(model, QWEN_PRICING["qwen-plus"])
                    input_cost = (input_tokens / 1000) * pricing["input"]
                    output_cost = (output_tokens / 1000) * pricing["output"]
                    cost = input_cost + output_cost
                    
                    print(f"\n💰 费用 (元):")
                    print(f"   输入: {input_cost:.6f}")
                    print(f"   输出: {output_cost:.6f}")
                    print(f"   总计: {cost:.6f}")
                    
                    total_input_tokens += input_tokens
                    total_output_tokens += output_tokens
                    total_cost += cost
                else:
                    print("⚠️  未获取到usage信息")
            else:
                print(f"❌ 调用失败: {response.code} - {response.message}")
                
        except Exception as e:
            print(f"❌ 异常: {str(e)}")
    
    print("\n" + "=" * 60)
    print("📊 本次测试总计")
    print("=" * 60)
    print(f"输入Token: {total_input_tokens}")
    print(f"输出Token: {total_output_tokens}")
    print(f"总Token: {total_input_tokens + total_output_tokens}")
    print(f"总费用: {total_cost:.6f} 元")
    print("\n💡 提示: 请登录阿里云DashScope控制台查看实际账单:")
    print("   https://dashscope.console.aliyun.com/")

if __name__ == "__main__":
    test_with_dashscope()
