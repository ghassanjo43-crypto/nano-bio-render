"""
Design Export Module
Handles exporting designs in multiple formats: JSON, CSV, PDF
"""

import json
import csv
import io
from datetime import datetime
from pathlib import Path
import streamlit as st


def export_design_as_json(design: dict, design_name: str = None) -> str:
    """
    Export design as JSON string.
    
    Args:
        design: Design dictionary with all parameters
        design_name: Name of the design (optional)
    
    Returns:
        JSON string of the design
    """
    export_data = {
        "metadata": {
            "exported_at": datetime.now().isoformat(),
            "app_version": "1.0.0",
            "design_name": design_name or "Untitled Design"
        },
        "design": design
    }
    
    return json.dumps(export_data, indent=2)


def export_design_as_csv(design: dict, design_name: str = None) -> str:
    """
    Export design as CSV format.
    
    Args:
        design: Design dictionary with all parameters
        design_name: Name of the design (optional)
    
    Returns:
        CSV string of the design
    """
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow(["Design Export - " + (design_name or "Untitled Design")])
    writer.writerow(["Exported", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
    writer.writerow([])
    
    # Design parameters
    writer.writerow(["Parameter", "Value"])
    for key, value in design.items():
        # Handle list values (like FunctionalGroups, SurfaceCoating)
        if isinstance(value, list):
            value_str = ", ".join(str(v) for v in value)
        else:
            value_str = str(value)
        writer.writerow([key, value_str])
    
    return output.getvalue()


def create_pdf_report(design: dict, design_name: str = None, include_recommendations: bool = True) -> bytes:
    """
    Create a PDF report of the design.
    Requires reportlab: pip install reportlab
    
    Args:
        design: Design dictionary
        design_name: Name of the design
        include_recommendations: Whether to include recommendations
    
    Returns:
        PDF bytes
    """
    try:
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
        from reportlab.lib.units import inch
        from core.scoring import compute_impact, get_recommendations
    except ImportError:
        raise ImportError(
            "reportlab is required for PDF export. Install with: pip install reportlab"
        )
    
    # Create PDF in memory
    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(pdf_buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1976d2'),
        spaceAfter=30,
        alignment=1  # Center
    )
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#004E89'),
        spaceAfter=12,
        spaceBefore=12
    )
    
    # Build story
    story = []
    
    # Title
    story.append(Paragraph(design_name or "Nanoparticle Design Report", title_style))
    story.append(Spacer(1, 0.2*inch))
    
    # Metadata
    metadata_data = [
        ["Export Date", datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
        ["Design Name", design_name or "Untitled Design"],
        ["App", "NanoBio Studio v1.0"]
    ]
    metadata_table = Table(metadata_data, colWidths=[2*inch, 4*inch])
    metadata_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f0f0')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey)
    ]))
    story.append(metadata_table)
    story.append(Spacer(1, 0.3*inch))
    
    # Design Parameters Section
    story.append(Paragraph("Design Parameters", heading_style))
    
    # Organize parameters by category
    core_params = [
        "Material", "Size", "Target", "Charge", "PDI", "HydrodynamicSize"
    ]
    
    material_params = [
        "CrystallinityIndex", "PorosityLevel", "PoreSize", "SurfaceCoating",
        "CoatingThickness", "FunctionalGroups", "Hydrophobicity", "SurfaceRoughness",
        "ZetaPotentialStability"
    ]
    
    surface_params = [
        "SurfaceArea", "Ligand", "LigandDensity", "Receptor", "ReceptorBinding"
    ]
    
    payload_params = [
        "Encapsulation", "Stability", "DegradationTime", "ReleaseProfile",
        "ReleasePredictability"
    ]
    
    # Core Properties
    story.append(Paragraph("Core Properties", ParagraphStyle(
        'SubHeading', parent=styles['Heading3'], fontSize=11, textColor=colors.HexColor('#333')))
    )
    core_data = [["Parameter", "Value"]]
    for param in core_params:
        if param in design:
            value = design[param]
            if isinstance(value, list):
                value = ", ".join(str(v) for v in value)
            core_data.append([param, str(value)])
    
    core_table = Table(core_data, colWidths=[2.5*inch, 3.5*inch])
    core_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1976d2')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9f9f9')])
    ]))
    story.append(core_table)
    story.append(Spacer(1, 0.2*inch))
    
    # Material Properties
    story.append(Paragraph("Material Properties", ParagraphStyle(
        'SubHeading', parent=styles['Heading3'], fontSize=11, textColor=colors.HexColor('#333')))
    )
    material_data = [["Parameter", "Value"]]
    for param in material_params:
        if param in design:
            value = design[param]
            if isinstance(value, list):
                value = ", ".join(str(v) for v in value)
            material_data.append([param, str(value)])
    
    material_table = Table(material_data, colWidths=[2.5*inch, 3.5*inch])
    material_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#004E89')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9f9f9')])
    ]))
    story.append(material_table)
    story.append(Spacer(1, 0.2*inch))
    
    # Impact Metrics
    try:
        impact = compute_impact(design)
        story.append(Paragraph("Impact Metrics", heading_style))
        
        impact_data = [
            ["Metric", "Value"],
            ["Delivery Efficiency", f"{impact.get('Delivery', 0):.1f}%"],
            ["Toxicity Score", f"{impact.get('Toxicity', 0):.2f}/10"],
            ["Manufacturing Cost", f"${impact.get('Cost', 0):.1f}"],
        ]
        
        impact_table = Table(impact_data, colWidths=[2.5*inch, 3.5*inch])
        impact_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#28a745')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9f9f9')])
        ]))
        story.append(impact_table)
        story.append(Spacer(1, 0.2*inch))
    except:
        pass
    
    # Recommendations
    if include_recommendations:
        try:
            recommendations = get_recommendations(design)
            if recommendations:
                story.append(Paragraph("Recommendations", heading_style))
                for rec in recommendations:
                    story.append(Paragraph(f"• {rec}", styles['Normal']))
                    story.append(Spacer(1, 0.05*inch))
                story.append(Spacer(1, 0.1*inch))
        except:
            pass
    
    # Footer
    story.append(Spacer(1, 0.2*inch))
    story.append(Paragraph(
        "<font size=8><i>This design report was generated by NanoBio Studio. "
        "Please validate all designs experimentally before use.</i></font>",
        styles['Normal']
    ))
    
    # Build PDF
    doc.build(story)
    pdf_buffer.seek(0)
    return pdf_buffer.getvalue()


def get_download_filename(design_name: str = None, format_type: str = "json") -> str:
    """
    Generate a download filename for the design.
    
    Args:
        design_name: Name of the design
        format_type: File format (json, csv, pdf)
    
    Returns:
        Filename with timestamp
    """
    name = design_name or "design"
    name = name.replace(" ", "_").lower()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    extensions = {"json": "json", "csv": "csv", "pdf": "pdf"}
    ext = extensions.get(format_type, format_type)
    return f"{name}_{timestamp}.{ext}"


def render_export_controls(design: dict, design_name: str = "My Design"):
    """
    Render export UI controls in the app.
    
    Args:
        design: The design dictionary to export
        design_name: Name of the design
    """
    st.markdown("### 📥 Export Design")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📄 Export as JSON", use_container_width=True):
            try:
                json_data = export_design_as_json(design, design_name)
                st.download_button(
                    label="Download JSON",
                    data=json_data,
                    file_name=get_download_filename(design_name, "json"),
                    mime="application/json",
                    use_container_width=True
                )
                st.success("JSON ready for download!")
            except Exception as e:
                st.error(f"Error exporting JSON: {str(e)}")
    
    with col2:
        if st.button("📊 Export as CSV", use_container_width=True):
            try:
                csv_data = export_design_as_csv(design, design_name)
                st.download_button(
                    label="Download CSV",
                    data=csv_data,
                    file_name=get_download_filename(design_name, "csv"),
                    mime="text/csv",
                    use_container_width=True
                )
                st.success("CSV ready for download!")
            except Exception as e:
                st.error(f"Error exporting CSV: {str(e)}")
    
    with col3:
        if st.button("📑 Export as PDF", use_container_width=True):
            try:
                pdf_data = create_pdf_report(design, design_name)
                st.download_button(
                    label="Download PDF",
                    data=pdf_data,
                    file_name=get_download_filename(design_name, "pdf"),
                    mime="application/pdf",
                    use_container_width=True
                )
                st.success("PDF ready for download!")
            except ImportError:
                st.warning("📦 PDF export requires: `pip install reportlab`")
            except Exception as e:
                st.error(f"Error exporting PDF: {str(e)}")


def render_quick_export(design: dict, design_name: str = "design"):
    """
    Render a compact export section for sidebars or small spaces.
    
    Args:
        design: The design dictionary
        design_name: Name of the design
    """
    st.markdown("**📥 Quick Export**")
    
    export_format = st.selectbox(
        "Format",
        ["JSON", "CSV", "PDF"],
        label_visibility="collapsed"
    )
    
    if st.button("Export", use_container_width=True):
        try:
            if export_format == "JSON":
                data = export_design_as_json(design, design_name)
                filename = get_download_filename(design_name, "json")
                mime = "application/json"
            elif export_format == "CSV":
                data = export_design_as_csv(design, design_name)
                filename = get_download_filename(design_name, "csv")
                mime = "text/csv"
            else:  # PDF
                data = create_pdf_report(design, design_name)
                filename = get_download_filename(design_name, "pdf")
                mime = "application/pdf"
            
            st.download_button(
                label=f"Download {export_format}",
                data=data,
                file_name=filename,
                mime=mime,
                use_container_width=True
            )
        except Exception as e:
            st.error(f"Export failed: {str(e)}")
