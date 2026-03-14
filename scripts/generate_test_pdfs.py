#!/usr/bin/env python3
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from datetime import datetime, timedelta
import os

def create_valid_order_pdf(output_path):
    doc = SimpleDocTemplate(output_path, pagesize=letter)
    story = []
    styles = getSampleStyleSheet()
    
    story.append(Paragraph("<b>制造业采购订单</b>", styles['Title']))
    story.append(Paragraph(f"订单编号: PO-2026-{datetime.now().strftime('%m%d')}-001", styles['Heading2']))
    story.append(Paragraph(f"客户名称: 上海机械制造有限公司", styles['Normal']))
    story.append(Paragraph(f"下单日期: {datetime.now().strftime('%Y年%m月%d日')}", styles['Normal']))
    story.append(Paragraph("", styles['Normal']))
    
    data = [
        ['序号', '物料名称', '规格型号', '数量', '单位', '单价', '交期'],
        ['1', '不锈钢螺丝', 'M8x30', '1000', '个', '0.50', (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')],
        ['2', '铝合金板', '6061-T6 2mm', '50', '平方米', '180.00', (datetime.now() + timedelta(days=10)).strftime('%Y-%m-%d')],
        ['3', '伺服电机', '松下 MSME042G1', '5', '台', '3500.00', (datetime.now() + timedelta(days=14)).strftime('%Y-%m-%d')],
        ['4', '轴承', '6204-2RS', '200', '个', '8.50', (datetime.now() + timedelta(days=5)).strftime('%Y-%m-%d')],
    ]
    
    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.grey),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 12),
        ('BOTTOMPADDING', (0,0), (-1,0), 12),
        ('BACKGROUND', (0,1), (-1,-1), colors.beige),
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('FONTSIZE', (0,1), (-1,-1), 10),
    ]))
    
    story.append(table)
    story.append(Paragraph("", styles['Normal']))
    story.append(Paragraph("备注: 请确保按时交货，如有问题请联系采购部。", styles['Normal']))
    
    doc.build(story)

def create_invalid_order_pdf(output_path):
    doc = SimpleDocTemplate(output_path, pagesize=letter)
    story = []
    styles = getSampleStyleSheet()
    
    story.append(Paragraph("<b>年度工作总结报告</b>", styles['Title']))
    story.append(Paragraph(f"报告日期: {datetime.now().strftime('%Y年%m月%d日')}", styles['Heading2']))
    story.append(Paragraph("", styles['Normal']))
    
    story.append(Paragraph("<b>一、工作回顾</b>", styles['Heading3']))
    story.append(Paragraph("在过去的一年里，我们团队在公司领导的正确指导下，圆满完成了各项工作任务。", styles['Normal']))
    story.append(Paragraph("", styles['Normal']))
    
    story.append(Paragraph("<b>二、主要成果</b>", styles['Heading3']))
    story.append(Paragraph("1. 产品销售额同比增长30%", styles['Normal']))
    story.append(Paragraph("2. 客户满意度提升至95%", styles['Normal']))
    story.append(Paragraph("3. 新产品研发项目顺利完成", styles['Normal']))
    story.append(Paragraph("", styles['Normal']))
    
    story.append(Paragraph("<b>三、未来计划</b>", styles['Heading3']))
    story.append(Paragraph("在新的一年里，我们将继续努力，争取更大的进步。", styles['Normal']))
    
    doc.build(story)

if __name__ == "__main__":
    valid_path = "/Users/cmh/Documents/AGENT_project/data/sample_orders/valid_manufacturing_order.pdf"
    invalid_path = "/Users/cmh/Documents/AGENT_project/data/sample_orders/invalid_document.pdf"
    
    create_valid_order_pdf(valid_path)
    print(f"✅ 有效的订单PDF已生成: {valid_path}")
    
    create_invalid_order_pdf(invalid_path)
    print(f"✅ 无效的PDF已生成: {invalid_path}")
