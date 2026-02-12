from flask import Blueprint, render_template, request, flash, redirect, url_for, session, make_response, current_app
from app.db import get_db
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, Frame, PageTemplate, NextPageTemplate
from datetime import datetime
import os
from app.services.pdf_service import add_watermark
from app.utils.decorators import role_required

relatorio_bp = Blueprint("relatorio", __name__)

@relatorio_bp.route('/relatorio', methods=['GET', 'POST'])
@role_required('assent', 'jur', 'admin')
def relatorios():
    if request.method == 'POST':
        empresa_id = request.form.get('empresa')
        if not empresa_id:
            flash("Selecione uma empresa.", "warning")
            return redirect(url_for('relatorios'))
        try:
            with get_db() as db:
                with db.cursor(dictionary=True) as cursor:
                    cursor.execute("SELECT * FROM municipal_lots WHERE id = %s", (int(empresa_id),))
                    lot = cursor.fetchone()
            if not lot: return "Empresa não encontrada.", 404
            from reportlab.lib.units import inch
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            if not hasattr(pdfmetrics, '_fonts'):
                from reportlab.pdfbase import pdfmetrics
            buffer = BytesIO()
            doc = SimpleDocTemplate(
                buffer,
                pagesize=A4,
                leftMargin=72,
                rightMargin=72,
                topMargin=120,
                bottomMargin=72
            )

            # Frame onde o conteúdo será desenhado
            frame = Frame(
                doc.leftMargin,
                doc.bottomMargin,
                doc.width,
                doc.height,
                id='normal'
            )

            # Template com marca d’água → será usado em TODAS as páginas
            template = PageTemplate(
                id='watermark_template',
                frames=[frame],
                onPage=add_watermark
            )
            doc.addPageTemplates([template])

            # Estilos
            styles = getSampleStyleSheet()
            font_title = 'Helvetica-Bold'
            font_normal = 'Helvetica'

            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontName=font_title,
                fontSize=16,
                leading=22,
                alignment=1,
                spaceAfter=20,
                textColor=colors.HexColor('#1a233a')
            )

            subtitle_style = ParagraphStyle(
                'Subtitle',
                parent=styles['Normal'],
                fontName=font_title,
                fontSize=12,
                leading=16,
                alignment=1,
                spaceAfter=10,
                textColor=colors.HexColor('#374151')
            )

            normal_style = ParagraphStyle(
                'CustomNormal',
                parent=styles['Normal'],
                fontName=font_normal,
                fontSize=10,
                leading=14,
                spaceBefore=0,
                spaceAfter=0
            )

            cell_style = ParagraphStyle(
                'CellStyle',
                parent=styles['Normal'],
                fontName=font_normal,
                fontSize=9,
                leading=12,
                wordWrap='CJK'
            )

            # Monta story
            story = []

            # Logo no topo
            logo_path = os.path.join(current_app.root_path, 'static', 'logo_codego.png')
            if os.path.exists(logo_path):
                logo = Image(logo_path, width=300, height=60, hAlign='CENTER')
                story.append(logo)
                story.append(Spacer(1, 20))

            # Título
            story.append(Paragraph("RELATÓRIO DE ASSENTAMENTO", title_style))
            story.append(Paragraph(f"Relatório: {lot.get('empresa', 'N/A')}", title_style))
            story.append(Spacer(1, 12))

            # Tabela
            data = [["Campo", "Valor"]]
            for k, v in lot.items():
                campo = str(k).replace('_', ' ').upper()
                valor = str(v) if v is not None else '-'
                data.append([
                    Paragraph(campo, cell_style),
                    Paragraph(valor, cell_style)
                ])

            table = Table(data, colWidths=[150, 350], repeatRows=1)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a233a')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), font_title),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('TOPPADDING', (0, 0), (-1, 0), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),

                ('FONTNAME', (0, 1), (-1, -1), font_normal),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('VALIGN', (0, 1), (-1, -1), 'TOP'),
                ('TOPPADDING', (0, 1), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
                ('LEFTPADDING', (0, 1), (-1, -1), 6),
                ('RIGHTPADDING', (0, 1), (-1, -1), 6),
                ('BACKGROUND', (0, 1), (-1, -1), colors.transparent),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
            ]))
            story.append(table)

            # Rodapé
            footer_para = Paragraph(
                f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')} | Usuário: {session.get('username', 'sistema')}",
                ParagraphStyle(
                    'Footer',
                    parent=styles['Normal'],
                    fontName=font_normal,
                    fontSize=8,
                    alignment=2,
                    spaceBefore=10,
                    textColor=colors.grey
                )
            )
            story.append(Spacer(1, 10))
            story.append(footer_para)

            # Força o mesmo template em todas as páginas
            # (isso é o que faz o watermark aparecer em todas elas)
            story.insert(0, NextPageTemplate('watermark_template'))

            # Gera o PDF
            doc.build(story)

            # Envia o PDF
            buffer.seek(0)
            response = make_response(buffer.getvalue())
            response.headers['Content-Type'] = 'application/pdf'
            response.headers['Content-Disposition'] = f'inline; filename="relatorio_{empresa_id}.pdf"'
            return response
        except Exception as e: return f"Erro PDF: {e}"

    empresas = []
    empresas_info = {}

    try:
        with get_db() as db:
            with db.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT id, empresa FROM municipal_lots WHERE empresa != '-' ORDER BY empresa")
                empresas = cursor.fetchall()
                cursor.execute("SELECT empresa_id, descricao, caminho_imagem FROM empresa_infos")
                infos = cursor.fetchall()
        for row in infos:
            empresas_info[str(row['empresa_id'])] = {
                "descricao": row.get('descricao') or 'Sem descrição cadastrada.',
                "foto": row.get('caminho_imagem') or 'static/empresa-default.png',
            }
    except Exception as err:
        print("Erro ao carregar dados:", err)
    template = 'relatorios_jur.html' if session.get('role') == 'jur' else 'relatorios.html'
    return render_template(template, empresas=empresas, empresas_info=empresas_info)