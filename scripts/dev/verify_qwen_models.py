#!/usr/bin/env python3
import os
import sys
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

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

def verify_model_config():
    print("=" * 60)
    print("📋 模型配置检查")
    print("=" * 60)
    
    config = {
        "QWEN_API_KEY": os.getenv("QWEN_API_KEY"),
        "QWEN_BASE_URL": os.getenv("QWEN_BASE_URL"),
        "QWEN_MODEL_MAX": os.getenv("QWEN_MODEL_MAX", "qwen-max"),
        "QWEN_MODEL_PLUS": os.getenv("QWEN_MODEL_PLUS", "qwen-plus"),
        "QWEN_MODEL_VL": os.getenv("QWEN_MODEL_VL", "qwen-vl-plus")
    }
    
    for key, value in config.items():
        if key == "QWEN_API_KEY" and value:
            masked = value[:8] + "*" * (len(value) - 16) + value[-8:] if len(value) > 16 else "***"
            print(f"✅ {key}: {masked}")
        elif value:
            print(f"✅ {key}: {value}")
        else:
            print(f"❌ {key}: 未设置")
    
    print()
    return config

def test_single_model(model_name, api_key, base_url, test_message):
    print(f"\n🔍 测试模型: {model_name}")
    print("-" * 60)
    
    try:
        llm = ChatOpenAI(
            model=model_name,
            api_key=api_key,
            base_url=base_url,
            temperature=0,
            max_tokens=100
        )
        
        result = llm.invoke(test_message)
        
        print(f"✅ 模型调用成功！")
        print(f"📤 输入: {test_message}")
        print(f"📥 输出: {result.content}")
        
        usage_metadata = getattr(result, 'usage_metadata', None)
        if usage_metadata:
            input_tokens = usage_metadata.get('input_tokens', 0)
            output_tokens = usage_metadata.get('output_tokens', 0)
            total_tokens = usage_metadata.get('total_tokens', 0)
            
            print(f"\n📊 Token统计:")
            print(f"   输入Token: {input_tokens}")
            print(f"   输出Token: {output_tokens}")
            print(f"   总计Token: {total_tokens}")
            
            pricing = QWEN_PRICING.get(model_name, QWEN_PRICING["qwen-plus"])
            input_cost = (input_tokens / 1000) * pricing["input"]
            output_cost = (output_tokens / 1000) * pricing["output"]
            total_cost = input_cost + output_cost
            
            print(f"\n💰 费用估算 (元):")
            print(f"   输入费用: {input_cost:.6f}")
            print(f"   输出费用: {output_cost:.6f}")
            print(f"   总费用: {total_cost:.6f}")
            
            return {
                "success": True,
                "model": model_name,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
                "cost": total_cost
            }
        else:
            print("⚠️  未获取到token使用信息")
            return {
                "success": True,
                "model": model_name,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "cost": 0
            }
            
    except Exception as e:
        print(f"❌ 模型调用失败: {str(e)}")
        return {
            "success": False,
            "model": model_name,
            "error": str(e)
        }

def main():
    print("\n" + "=" * 60)
    print("🤖 Qwen模型验证与Token计算工具")
    print("=" * 60)
    
    config = verify_model_config()
    
    if not config["QWEN_API_KEY"]:
        print("❌ 未设置API密钥，请检查.env文件")
        return
    
    test_messages = [
        "你好，请用一句话介绍你自己",
        "Hello, please introduce yourself in one sentence"
    ]
    
    models_to_test = [
        config["QWEN_MODEL_MAX"],
        config["QWEN_MODEL_PLUS"],
        config["QWEN_MODEL_VL"]
    ]
    
    results = []
    for model in models_to_test:
        if model:
            result = test_single_model(
                model, 
                config["QWEN_API_KEY"], 
                config["QWEN_BASE_URL"],
                test_messages[0]
            )
            results.append(result)
    
    print("\n" + "=" * 60)
    print("📋 测试总结")
    print("=" * 60)
    
    total_cost = 0
    total_tokens = 0
    success_count = 0
    
    for result in results:
        if result["success"]:
            success_count += 1
            total_cost += result["cost"]
            total_tokens += result["total_tokens"]
            print(f"✅ {result['model']}: 成功")
        else:
            print(f"❌ {result['model']}: 失败 - {result.get('error', '未知错误')}")
    
    print(f"\n📊 总计:")
    print(f"   成功模型数: {success_count}/{len(results)}")
    print(f"   总Token数: {total_tokens}")
    print(f"   总费用: {total_cost:.6f} 元")
    
    print("\n💡 提示: 每次实际调用都会产生费用，请合理测试！")

if __name__ == "__main__":
    main()
