#!/usr/bin/env python3
import os
from pathlib import Path
from dotenv import load_dotenv
import base64
from PIL import Image, ImageDraw, ImageFont
import tempfile

load_dotenv()
PROJECT_ROOT = Path(__file__).resolve().parents[2]

def create_test_image(output_path):
    img = Image.new('RGB', (800, 400), color='#f0f5f9')
    draw = ImageDraw.Draw(img)
    
    try:
        font_title = ImageFont.truetype('/System/Library/Fonts/STHeiti Light.ttc', 36)
        font_text = ImageFont.truetype('/System/Library/Fonts/STHeiti Light.ttc', 20)
    except:
        font_title = ImageFont.load_default()
        font_text = ImageFont.load_default()
    
    draw.text((400, 50), '测试订单', font=font_title, fill='#336699', anchor='mm')
    
    text = [
        '物料名称: 不锈钢螺丝',
        '规格型号: M8x30',
        '数量: 1000个',
        '单价: 0.50元'
    ]
    
    for i, line in enumerate(text):
        draw.text((50, 150 + i * 40), line, font=font_text, fill='#333')
    
    img.save(output_path)
    return output_path

def encode_image(image_path):
    with open(image_path, 'rb') as f:
        return base64.b64encode(f.read()).decode('utf-8')

def test_qwen_vl_plus():
    print("=" * 60)
    print("🤖 测试 qwen-vl-plus 视觉语言模型")
    print("=" * 60)
    
    try:
        import dashscope
    except ImportError:
        print("❌ dashscope库未安装")
        return
    
    api_key = os.getenv("QWEN_API_KEY")
    if not api_key:
        print("❌ 未设置QWEN_API_KEY")
        return
    
    dashscope.api_key = api_key
    
    test_image_path = str(PROJECT_ROOT / "data" / "test_order_image.jpg")
    create_test_image(test_image_path)
    print(f"✅ 测试图片已创建: {test_image_path}")
    
    base64_image = encode_image(test_image_path)
    
    print(f"\n🔍 调用 qwen-vl-plus...")
    print("-" * 60)
    
    try:
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "请识别这张图片中的内容，提取出物料名称、规格型号、数量和单价"},
                    {"image": f"data:image/jpeg;base64,{base64_image}"}
                ]
            }
        ]
        
        response = dashscope.MultiModalConversation.call(
            model="qwen-vl-plus",
            messages=messages
        )
        
        if response.status_code == 200:
            print("✅ qwen-vl-plus 调用成功！")
            print(f"\n📤 输入: 图片包含订单信息")
            print(f"\n📥 输出:")
            
            print("完整响应结构:")
            print(response)
            print("\n")
            
            output_content = response.output
            if hasattr(output_content, 'choices') and len(output_content.choices) > 0:
                choice = output_content.choices[0]
                if hasattr(choice, 'message'):
                    message = choice.message
                    if hasattr(message, 'content'):
                        content_list = message.content
                        if isinstance(content_list, list):
                            for content_item in content_list:
                                if isinstance(content_item, dict) and 'text' in content_item:
                                    print(content_item['text'])
                                elif hasattr(content_item, 'text'):
                                    print(content_item.text)
            
            if hasattr(response, 'usage'):
                input_tokens = response.usage.input_tokens
                output_tokens = response.usage.output_tokens
                total_tokens = response.usage.total_tokens
                
                print(f"\n📊 Token统计:")
                print(f"   输入Token: {input_tokens}")
                print(f"   输出Token: {output_tokens}")
                print(f"   总计Token: {total_tokens}")
                
                input_cost = (input_tokens / 1000) * 0.008
                output_cost = (output_tokens / 1000) * 0.02
                cost = input_cost + output_cost
                
                print(f"\n💰 费用 (元):")
                print(f"   输入: {input_cost:.6f}")
                print(f"   输出: {output_cost:.6f}")
                print(f"   总计: {cost:.6f}")
        else:
            print(f"❌ 调用失败: {response.code} - {response.message}")
            
    except Exception as e:
        print(f"❌ 异常: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_qwen_vl_plus()
