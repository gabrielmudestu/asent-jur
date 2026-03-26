from datetime import datetime
from io import BytesIO
import os

from flask import Blueprint, current_app, flash, make_response, redirect, render_template, request, session, url_for
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.db import get_db
from app.services.pdf_service import add_watermark
from app.utils.decorators import role_required

relatorio_bp = Blueprint("relatorio", __name__)


@relatorio_bp.route('/relatorio', methods=['GET', 'POST'])
@role_required('assent', 'jur', 'admin', 'assent_gestor', 'jur_gestor')
def relatorios():
    role = session.get('role')
    modo = request.args.get('modo')

    if not modo:
        modo = 'jur' if role in ('jur', 'jur_gestor') else 'assent'

    if request.method == 'POST':
        empresa_id = request.form.get('empresa')
        if not empresa_id:
            flash("Selecione uma empresa.", "warning")
            return redirect(url_for('relatorio.relatorios', modo=modo))

        try:
            with get_db() as db:
                with db.cursor(dictionary=True) as cursor:
                    cursor.execute("SELECT * FROM municipal_lots WHERE id = %s", (int(empresa_id),))
                    lot = cursor.fetchone()
                    cursor.execute(
                        """
                        SELECT numero_processo, tipo_processo, status, assunto_judicial,
                               valor_da_causa, recurso_acionado, tipo_recurso
                        FROM processos
                        WHERE empresa_id = %s
                        ORDER BY id
                        """,
                        (int(empresa_id),)
                    )
                    processos = cursor.fetchall()

            if not lot:
                return "Empresa não encontrada.", 404

            buffer = BytesIO()
            doc = SimpleDocTemplate(
                buffer,
                pagesize=A4,
                leftMargin=72,
                rightMargin=72,
                topMargin=120,
                bottomMargin=72
            )

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

            story = []

            logo_path = os.path.join(current_app.root_path, 'static', 'logo_codego.png')
            if os.path.exists(logo_path):
                logo = Image(logo_path, width=300, height=60, hAlign='CENTER')
                story.append(logo)
                story.append(Spacer(1, 20))

            titulo_relatorio = "RELATÓRIO JURÍDICO" if modo == 'jur' else "RELATÓRIO DE ASSENTAMENTO"
            story.append(Paragraph(titulo_relatorio, title_style))
            story.append(Paragraph(f"Relatório: {lot.get('empresa', 'N/A')}", title_style))
            story.append(Spacer(1, 12))

            data = [["Campo", "Valor"]]
            campos_juridicos_legados = {'processo_judicial', 'status', 'assunto_judicial', 'valor_da_causa'}
            for chave, valor in lot.items():
                if chave == 'id' or chave in campos_juridicos_legados:
                    continue
                data.append([
                    Paragraph(str(chave).replace('_', ' ').upper(), cell_style),
                    Paragraph(str(valor) if valor is not None else '-', cell_style)
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

            process_labels = {
                'numero_processo': 'NUMERO DO PROCESSO',
                'tipo_processo': 'TIPO DE PROCESSO',
                'status': 'STATUS',
                'assunto_judicial': 'ASSUNTO JUDICIAL',
                'valor_da_causa': 'VALOR DA CAUSA',
                'recurso_acionado': 'RECURSO ACIONADO',
                'tipo_recurso': 'TIPO DE RECURSO',
            }

            story.append(Spacer(1, 18))
            story.append(Paragraph("PROCESSOS JURIDICOS", subtitle_style))

            if processos:
                for idx, processo in enumerate(processos, start=1):
                    story.append(Paragraph(f"Processo {idx}", subtitle_style))

                    processo_data = [["Campo", "Valor"]]
                    for chave, label in process_labels.items():
                        valor = processo.get(chave)
                        if chave == 'recurso_acionado':
                            valor = 'SIM' if valor else 'NAO'
                        valor = str(valor) if valor not in (None, '') else '-'
                        processo_data.append([
                            Paragraph(label, cell_style),
                            Paragraph(valor, cell_style)
                        ])

                    processo_table = Table(processo_data, colWidths=[150, 350], repeatRows=1)
                    processo_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#7f1d1d')),
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
                    story.append(processo_table)
                    story.append(Spacer(1, 12))
            else:
                story.append(Paragraph("Nenhum processo juridico cadastrado para esta empresa.", normal_style))

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

            doc.build(story, onFirstPage=add_watermark, onLaterPages=add_watermark)

            buffer.seek(0)
            response = make_response(buffer.getvalue())
            response.headers['Content-Type'] = 'application/pdf'
            response.headers['Content-Disposition'] = f'inline; filename="relatorio_{empresa_id}.pdf"'
            return response
        except Exception as e:
            return f"Erro PDF: {e}"

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

    template = 'relatorios_jur.html' if modo == 'jur' else 'relatorios.html'
    return render_template(template, empresas=empresas, empresas_info=empresas_info)
