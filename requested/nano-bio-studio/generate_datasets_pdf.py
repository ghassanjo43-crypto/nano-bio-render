#!/usr/bin/env python
"""Generate PDF report of NanoBio Studio datasets"""

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from datetime import datetime

# Create PDF
pdf_path = 'NanoBio_Studio_Datasets_Summary.pdf'
doc = SimpleDocTemplate(pdf_path, pagesize=letter, topMargin=0.7*inch, bottomMargin=0.7*inch,
                        leftMargin=0.6*inch, rightMargin=0.6*inch)
story = []
styles = getSampleStyleSheet()

# Custom Styles
title_style = ParagraphStyle(
    'ReportTitle',
    parent=styles['Heading1'],
    fontSize=24,
    textColor=colors.HexColor('#1a237e'),
    spaceAfter=10,
    alignment=TA_CENTER,
    fontName='Helvetica-Bold'
)

subtitle_style = ParagraphStyle(
    'Subtitle',
    parent=styles['Normal'],
    fontSize=12,
    textColor=colors.HexColor('#667eea'),
    spaceAfter=4,
    alignment=TA_CENTER,
    fontName='Helvetica'
)

section_style = ParagraphStyle(
    'SectionHead',
    parent=styles['Heading2'],
    fontSize=13,
    textColor=colors.HexColor('#1a237e'),
    spaceAfter=8,
    spaceBefore=8,
    fontName='Helvetica-Bold'
)

normal_style = ParagraphStyle(
    'Normal',
    parent=styles['Normal'],
    fontSize=10,
    alignment=TA_LEFT,
    spaceAfter=6
)

# Header
story.append(Paragraph('NanoBio Studio', title_style))
story.append(Paragraph('Implemented Training Datasets - Volume Summary', subtitle_style))
timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
story.append(Paragraph(f'Report Generated: {timestamp}', normal_style))
story.append(Spacer(1, 0.2*inch))

# Main Dataset Table
story.append(Paragraph('Primary Training Datasets', section_style))

main_data = [
    ['Dataset Name', 'Type', 'Samples', 'File Size', 'Status'],
    ['comprehensive_lnp_dataset.csv', 'Primary LNP', '202', '30.89 KB', 'Active'],
    ['sample_lnp_dataset.csv', 'Test/Demo', '15', '3.22 KB', 'Active'],
    ['all_external_sources_dataset_*.csv', 'Consolidated', '1,650', '532.49 KB', 'Active'],
    ['faers_dataset_*.csv', 'Safety (FDA)', '500', '138.07 KB', 'Active'],
    ['toxcast_dataset_*.csv', 'Toxicity', '100', '34.56 KB', 'Active'],
    ['chemspider_dataset_*.csv', 'Chemical Data', '300', '95.57 KB', 'Active'],
    ['geo_dataset_*.csv', 'Gene Expression', '300', '88.34 KB', 'Active'],
    ['clinical_trials_dataset_*.csv', 'Clinical Data', '250', '83.00 KB', 'Active'],
    ['pdb_dataset_*.csv', 'Structural Data', '200', '77.65 KB', 'Active'],
]

main_table = Table(main_data, colWidths=[2.2*inch, 1.5*inch, 1*inch, 1*inch, 1*inch])
main_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a237e')),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
    ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 0), (-1, 0), 10),
    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9f9f9')]),
    ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
    ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
    ('FONTSIZE', (0, 1), (-1, -1), 9),
    ('PADDING', (0, 0), (-1, -1), 8),
    ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#cccccc')),
    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
]))
story.append(main_table)
story.append(Spacer(1, 0.2*inch))

# Statistics
story.append(Paragraph('Dataset Statistics', section_style))

stats_data = [
    ['Metric', 'Value'],
    ['Total Datasets', '9'],
    ['Total Samples', '4,117 samples'],
    ['Total Storage', '~1.08 MB'],
    ['Largest Dataset', 'all_external_sources_dataset (1,650 samples)'],
    ['Smallest Dataset', 'sample_lnp_dataset (15 samples)'],
    ['Primary Training Dataset', 'comprehensive_lnp_dataset (202 samples)'],
]

stats_table = Table(stats_data, colWidths=[3*inch, 3*inch])
stats_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#667eea')),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
    ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 0), (-1, 0), 10),
    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9f9f9')]),
    ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
    ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
    ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 1), (-1, -1), 9),
    ('PADDING', (0, 0), (-1, -1), 8),
    ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#cccccc')),
    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
]))
story.append(stats_table)
story.append(Spacer(1, 0.2*inch))

# Dataset Categories
story.append(Paragraph('Dataset Categories', section_style))

category1_title = '1. Primary LNP Training Data (217 samples)'
story.append(Paragraph(category1_title, ParagraphStyle('CategoryStyle', parent=styles['Normal'], fontSize=11, fontName='Helvetica-Bold', spaceAfter=6)))
story.append(Paragraph('• comprehensive_lnp_dataset.csv - 202 samples (main training corpus)', normal_style))
story.append(Paragraph('• sample_lnp_dataset.csv - 15 samples (quick testing)', normal_style))
story.append(Spacer(1, 0.1*inch))

category2_title = '2. External Integrated Sources (2,550 samples)'
story.append(Paragraph(category2_title, ParagraphStyle('CategoryStyle', parent=styles['Normal'], fontSize=11, fontName='Helvetica-Bold', spaceAfter=6)))
story.append(Paragraph('• FDA FAERS - 500 samples (drug safety monitoring)', normal_style))
story.append(Paragraph('• ChemSpider - 300 samples (chemical properties)', normal_style))
story.append(Paragraph('• Gene Expression (GEO) - 300 samples (efficacy data)', normal_style))
story.append(Paragraph('• Clinical Trials - 250 samples (clinical evidence)', normal_style))
story.append(Paragraph('• Toxicity (ToxCast) - 100 samples (toxicity prediction)', normal_style))
story.append(Paragraph('• PDB - 200 samples (molecular structures)', normal_style))
story.append(Paragraph('• Consolidated - 1,650 samples (all sources combined)', normal_style))
story.append(Spacer(1, 0.1*inch))

category3_title = '3. Usage in ML Training'
story.append(Paragraph(category3_title, ParagraphStyle('CategoryStyle', parent=styles['Normal'], fontSize=11, fontName='Helvetica-Bold', spaceAfter=6)))
story.append(Paragraph('• Dropdown options: my_dataset, toxicity_large, custom_data', normal_style))
story.append(Paragraph('• Users can upload additional datasets', normal_style))
story.append(Paragraph('• All external sources accessible programmatically', normal_style))
story.append(Spacer(1, 0.2*inch))

# Footer
footer_style = ParagraphStyle(
    'Footer',
    parent=styles['Normal'],
    fontSize=8,
    textColor=colors.grey,
    alignment=TA_CENTER
)

story.append(Paragraph('_' * 70, footer_style))
story.append(Paragraph('NanoBio Studio - Comprehensive Training Dataset Documentation', footer_style))
story.append(Paragraph('Total Training Capacity: 4,117+ samples across 9 datasets', footer_style))
story.append(Paragraph('Copyright 2026 NanoBio Studio | All Rights Reserved', footer_style))

# Generate PDF
doc.build(story)
print(f'PDF created successfully: {pdf_path}')
