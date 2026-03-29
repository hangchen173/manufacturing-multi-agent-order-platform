#!/usr/bin/env python3
from pathlib import Path
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from datetime import datetime, timedelta
import os
import platform

PROJECT_ROOT = Path(__file__).resolve().parents[2]

def register_chinese_fonts():
    system = platform.system()
    font_paths = []
    
    if system == 'Darwin':
        font_paths = [
            '/System/Library/Fonts/PingFang.ttc',
            '/System/Library/Fonts/STHeiti Light.ttc',
            '/System/Library/Fonts/Helvetica.ttc'
        ]
    elif system == 'Windows':
        font_paths = [
            'C:/Windows/Fonts/msyh.ttc',
            'C:/Windows/Fonts/simsun.ttc'
        ]
    else:
        font_paths = [
            '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
            '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
        ]
    
    font_registered = False
    for font_path in font_paths:
        if os.path.exists(font_path):
            try:
                pdfmetrics.registerFont(TTFont('ChineseFont', font_path))
                font_registered = True
                print(f"已注册字体: {font_path}")
                break
            except Exception as e:
                print(f"尝试注册字体 {font_path} 失败: {e}")
                continue
    
    return font_registered

def create_valid_order_pdf(output_path, use_chinese_font=False):
    doc = SimpleDocTemplate(output_path, pagesize=A4)
    story = []
    styles = getSampleStyleSheet()
    
    if use_chinese_font:
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Title'],
            fontName='ChineseFont',
            fontSize=18,
            spaceAfter=12
        )
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontName='ChineseFont',
            fontSize=14,
            spaceAfter=6
        )
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontName='ChineseFont',
            fontSize=10,
            spaceAfter=3
        )
    else:
        title_style = styles['Title']
        heading_style = styles['Heading2']
        normal_style = styles['Normal']
    
    story.append(Paragraph("<b>制造业采购订单</b>", title_style))
    story.append(Spacer(1, 6))
    story.append(Paragraph(f"订单编号: PO-2026-{datetime.now().strftime('%m%d')}-001", heading_style))
    story.append(Paragraph(f"客户名称: 上海机械制造有限公司", normal_style))
    story.append(Paragraph(f"下单日期: {datetime.now().strftime('%Y年%m月%d日')}", normal_style))
    story.append(Spacer(1, 12))
    
    data = [
        ['序号', '物料名称', '规格型号', '数量', '单位', '单价', '交期'],
        ['1', '不锈钢螺丝', 'M8x30', '1000', '个', '0.50', (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')],
        ['2', '铝合金板', '6061-T6 2mm', '50', '平方米', '180.00', (datetime.now() + timedelta(days=10)).strftime('%Y-%m-%d')],
        ['3', '伺服电机', '松下 MSME042G1', '5', '台', '3500.00', (datetime.now() + timedelta(days=14)).strftime('%Y-%m-%d')],
        ['4', '轴承', '6204-2RS', '200', '个', '8.50', (datetime.now() + timedelta(days=5)).strftime('%Y-%m-%d')],
    ]
    
    table = Table(data, colWidths=[40, 100, 100, 50, 40, 60, 80])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#336699')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold' if not use_chinese_font else 'ChineseFont'),
        ('FONTSIZE', (0,0), (-1,0), 11),
        ('BOTTOMPADDING', (0,0), (-1,0), 10),
        ('TOPPADDING', (0,0), (-1,0), 10),
        ('BACKGROUND', (0,1), (-1,-1), colors.HexColor('#f0f5f9')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('FONTSIZE', (0,1), (-1,-1), 9),
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica' if not use_chinese_font else 'ChineseFont'),
    ]))
    
    story.append(table)
    story.append(Spacer(1, 12))
    story.append(Paragraph("备注: 请确保按时交货，如有问题请联系采购部。", normal_style))
    
    doc.build(story)

def create_invalid_order_pdf(output_path, use_chinese_font=False):
    doc = SimpleDocTemplate(output_path, pagesize=A4)
    story = []
    styles = getSampleStyleSheet()
    
    if use_chinese_font:
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Title'],
            fontName='ChineseFont',
            fontSize=18,
            spaceAfter=12
        )
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading3'],
            fontName='ChineseFont',
            fontSize=12,
            spaceAfter=6
        )
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontName='ChineseFont',
            fontSize=10,
            spaceAfter=3
        )
    else:
        title_style = styles['Title']
        heading_style = styles['Heading3']
        normal_style = styles['Normal']
    
    story.append(Paragraph("<b>年度工作总结报告</b>", title_style))
    story.append(Spacer(1, 6))
    story.append(Paragraph(f"报告日期: {datetime.now().strftime('%Y年%m月%d日')}", heading_style))
    story.append(Spacer(1, 12))
    
    story.append(Paragraph("<b>一、工作回顾</b>", heading_style))
    story.append(Paragraph("在过去的一年里，我们团队在公司领导的正确指导下，圆满完成了各项工作任务。", normal_style))
    story.append(Spacer(1, 6))
    
    story.append(Paragraph("<b>二、主要成果</b>", heading_style))
    story.append(Paragraph("1. 产品销售额同比增长30%", normal_style))
    story.append(Paragraph("2. 客户满意度提升至95%", normal_style))
    story.append(Paragraph("3. 新产品研发项目顺利完成", normal_style))
    story.append(Spacer(1, 6))
    
    story.append(Paragraph("<b>三、未来计划</b>", heading_style))
    story.append(Paragraph("在新的一年里，我们将继续努力，争取更大的进步。", normal_style))
    
    doc.build(story)

if __name__ == "__main__":
    sample_orders_dir = PROJECT_ROOT / "data" / "sample_orders"
    sample_orders_dir.mkdir(parents=True, exist_ok=True)
    valid_path = str(sample_orders_dir / "valid_manufacturing_order.pdf")
    invalid_path = str(sample_orders_dir / "invalid_document.pdf")
    
    use_chinese = register_chinese_fonts()
    
    create_valid_order_pdf(valid_path, use_chinese)
    print(f"✅ 有效的订单PDF已生成: {valid_path}")
    
    create_invalid_order_pdf(invalid_path, use_chinese)
    print(f"✅ 无效的PDF已生成: {invalid_path}")
