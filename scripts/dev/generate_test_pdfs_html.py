#!/usr/bin/env python3
import os
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

def create_valid_order_html():
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>制造业采购订单</title>
    <style>
        body {{ font-family: "PingFang SC", "Microsoft YaHei", sans-serif; margin: 40px; }}
        h1 {{ text-align: center; color: #333; }}
        .info {{ margin-bottom: 20px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ border: 1px solid #ddd; padding: 12px; text-align: center; }}
        th {{ background-color: #336699; color: white; }}
        tr:nth-child(even) {{ background-color: #f0f5f9; }}
        .footer {{ margin-top: 30px; color: #666; }}
    </style>
</head>
<body>
    <h1>制造业采购订单</h1>
    <div class="info">
        <p><strong>订单编号:</strong> PO-2026-{datetime.now().strftime('%m%d')}-001</p>
        <p><strong>客户名称:</strong> 上海机械制造有限公司</p>
        <p><strong>下单日期:</strong> {datetime.now().strftime('%Y年%m月%d日')}</p>
    </div>
    <table>
        <tr>
            <th>序号</th>
            <th>物料名称</th>
            <th>规格型号</th>
            <th>数量</th>
            <th>单位</th>
            <th>单价</th>
            <th>交期</th>
        </tr>
        <tr>
            <td>1</td>
            <td>不锈钢螺丝</td>
            <td>M8x30</td>
            <td>1000</td>
            <td>个</td>
            <td>0.50</td>
            <td>{(datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')}</td>
        </tr>
        <tr>
            <td>2</td>
            <td>铝合金板</td>
            <td>6061-T6 2mm</td>
            <td>50</td>
            <td>平方米</td>
            <td>180.00</td>
            <td>{(datetime.now() + timedelta(days=10)).strftime('%Y-%m-%d')}</td>
        </tr>
        <tr>
            <td>3</td>
            <td>伺服电机</td>
            <td>松下 MSME042G1</td>
            <td>5</td>
            <td>台</td>
            <td>3500.00</td>
            <td>{(datetime.now() + timedelta(days=14)).strftime('%Y-%m-%d')}</td>
        </tr>
        <tr>
            <td>4</td>
            <td>轴承</td>
            <td>6204-2RS</td>
            <td>200</td>
            <td>个</td>
            <td>8.50</td>
            <td>{(datetime.now() + timedelta(days=5)).strftime('%Y-%m-%d')}</td>
        </tr>
    </table>
    <div class="footer">
        <p><strong>备注:</strong> 请确保按时交货，如有问题请联系采购部。</p>
    </div>
</body>
</html>
    """
    return html_content

def create_invalid_order_html():
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>年度工作总结报告</title>
    <style>
        body {{ font-family: "PingFang SC", "Microsoft YaHei", sans-serif; margin: 40px; }}
        h1 {{ text-align: center; color: #333; }}
        h2 {{ color: #336699; margin-top: 30px; }}
        .date {{ text-align: right; color: #666; margin-bottom: 30px; }}
        p {{ line-height: 1.8; }}
    </style>
</head>
<body>
    <h1>年度工作总结报告</h1>
    <div class="date">报告日期: {datetime.now().strftime('%Y年%m月%d日')}</div>
    
    <h2>一、工作回顾</h2>
    <p>在过去的一年里，我们团队在公司领导的正确指导下，圆满完成了各项工作任务。</p>
    
    <h2>二、主要成果</h2>
    <p>1. 产品销售额同比增长30%</p>
    <p>2. 客户满意度提升至95%</p>
    <p>3. 新产品研发项目顺利完成</p>
    
    <h2>三、未来计划</h2>
    <p>在新的一年里，我们将继续努力，争取更大的进步。</p>
</body>
</html>
    """
    return html_content

if __name__ == "__main__":
    try:
        import pdfkit
        
        valid_html = create_valid_order_html()
        invalid_html = create_invalid_order_html()
        
        sample_orders_dir = PROJECT_ROOT / "data" / "sample_orders"
        sample_orders_dir.mkdir(parents=True, exist_ok=True)
        valid_path = str(sample_orders_dir / "valid_manufacturing_order.pdf")
        invalid_path = str(sample_orders_dir / "invalid_document.pdf")
        
        options = {
            'encoding': 'UTF-8',
            'quiet': ''
        }
        
        pdfkit.from_string(valid_html, valid_path, options=options)
        print(f"✅ 有效的订单PDF已生成 (HTML版): {valid_path}")
        
        pdfkit.from_string(invalid_html, invalid_path, options=options)
        print(f"✅ 无效的PDF已生成 (HTML版): {invalid_path}")
        
    except ImportError:
        print("⚠️  pdfkit未安装，使用ReportLab版本已生成")
        print("   如需更好的字体效果，请运行: brew install wkhtmltopdf && pip install pdfkit")
