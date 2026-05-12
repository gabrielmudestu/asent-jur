from datetime import datetime
from io import BytesIO
import os

from flask import Blueprint, current_app, flash, make_response, redirect, render_template, request, session, url_for
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.db import get_db
from app.constants import LABELS
from app.services.juridico_schema_service import garantir_schema_juridico
from app.services.pdf_service import add_watermark
from app.utils.decorators import role_required

relatorio_bp = Blueprint("relatorio", __name__)

RELATORIO_EMPRESA_ORDEM = [
    'municipio',
    'distrito',
    'empresa',
    'cnpj',
    'ramo_de_atividade',
    'processo_sei',
    'status_de_assentamento',
    'acao_judicial',
    'imovel_regular_irregular',
    'quadra',
    'modulo_s',
    'qtd_modulos',
    'tamanho_m2',
    'matricula_s',
    'taxa_e_ocupacao_do_imovel',
    'empregos_gerados',
    'data_escrituracao',
    'data_contrato_de_compra_e_venda',
    'ultima_vistoria',
    'atualizado',
    'observacoes',
    'observacoes_1',
    'obsevacoes',
    'irregularidades',
    'observacoes_2',
    'observacoes_3',
]

RELATORIO_PROCESSO_LABELS = [
    ('numero_processo', 'Numero CNJ'),
    ('titulo', 'Titulo'),
    ('descricao', 'Descricao'),
    ('tipo_acao', 'Tipo de acao'),
    ('tribunal', 'Tribunal'),
    ('vara', 'Vara'),
    ('comarca', 'Comarca'),
    ('valor_da_causa', 'Valor da causa'),
    ('status', 'Status'),
    ('fase', 'Fase'),
    ('data_criacao', 'Data de criacao'),
    ('recurso_acionado', 'Recurso acionado'),
    ('tipo_recurso', 'Tipo de recurso'),
]


def valor_pdf(valor):
    if valor in (None, ''):
        return '-'
    if isinstance(valor, bool):
        return 'SIM' if valor else 'NAO'
    if isinstance(valor, int) and valor in (0, 1):
        return 'SIM' if valor else 'NAO'
    return str(valor)


def adicionar_tabela_chave_valor(story, dados, labels, cell_style, header_color='#1a233a'):
    tabela_dados = [["Campo", "Valor"]]
    for chave, label in labels:
        tabela_dados.append([
            Paragraph(label, cell_style),
            Paragraph(valor_pdf(dados.get(chave)), cell_style),
        ])

    tabela = Table(tabela_dados, colWidths=[150, 350], repeatRows=1)
    tabela.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(header_color)),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('VALIGN', (0, 1), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ('LEFTPADDING', (0, 1), (-1, -1), 6),
        ('RIGHTPADDING', (0, 1), (-1, -1), 6),
        ('BACKGROUND', (0, 1), (-1, -1), colors.transparent),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    story.append(tabela)


def adicionar_lista_eventos(story, titulo, eventos, subtitle_style, cell_style):
    story.append(Spacer(1, 16))
    story.append(Paragraph(titulo, subtitle_style))
    if not eventos:
        story.append(Paragraph("Nenhum registro.", cell_style))
        return

    linhas = [["Data", "Titulo", "Descricao"]]
    for evento in eventos:
        linhas.append([
            Paragraph(valor_pdf(evento.get('data_evento') or evento.get('created_at')), cell_style),
            Paragraph(valor_pdf(evento.get('titulo') or evento.get('categoria')), cell_style),
            Paragraph(valor_pdf(evento.get('descricao')), cell_style),
        ])

    tabela = Table(linhas, colWidths=[90, 140, 270], repeatRows=1)
    tabela.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#7f1d1d')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(tabela)


def gerar_pdf_processo(processo, partes, eventos, documentos):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=72, rightMargin=72, topMargin=120, bottomMargin=72)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'ProcessoTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=16,
        leading=22,
        alignment=1,
        spaceAfter=14,
        textColor=colors.HexColor('#1a233a')
    )
    subtitle_style = ParagraphStyle(
        'ProcessoSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        spaceAfter=8,
        textColor=colors.HexColor('#374151')
    )
    cell_style = ParagraphStyle(
        'ProcessoCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        wordWrap='CJK'
    )

    story = []
    logo_path = os.path.join(current_app.root_path, 'static', 'logo_codego.png')
    if os.path.exists(logo_path):
        story.append(Image(logo_path, width=300, height=60, hAlign='CENTER'))
        story.append(Spacer(1, 20))

    story.append(Paragraph("RELATORIO DO PROCESSO JURIDICO", title_style))
    story.append(Paragraph(valor_pdf(processo.get('numero_processo')), title_style))
    story.append(Spacer(1, 12))

    story.append(Paragraph("DADOS PRINCIPAIS", subtitle_style))
    adicionar_tabela_chave_valor(story, processo, RELATORIO_PROCESSO_LABELS, cell_style)

    story.append(Spacer(1, 16))
    story.append(Paragraph("PARTES", subtitle_style))
    partes_labels = [('papel', 'Papel'), ('nome', 'Nome'), ('tipo_parte', 'Tipo'), ('contato', 'Contato'), ('observacoes', 'Observacoes')]
    if partes:
        for parte in partes:
            adicionar_tabela_chave_valor(story, parte, partes_labels, cell_style, header_color='#002b5c')
            story.append(Spacer(1, 8))
    else:
        story.append(Paragraph("Nenhuma parte cadastrada.", cell_style))

    adicionar_lista_eventos(story, "PRAZOS", [e for e in eventos if e.get('categoria') == 'prazo'], subtitle_style, cell_style)
    adicionar_lista_eventos(story, "MOVIMENTACOES", [e for e in eventos if e.get('categoria') == 'movimentacao'], subtitle_style, cell_style)
    adicionar_lista_eventos(story, "DOCUMENTOS TEXTUAIS", [e for e in eventos if e.get('categoria') == 'documento'], subtitle_style, cell_style)

    story.append(Spacer(1, 16))
    story.append(Paragraph("ARQUIVOS ANEXADOS", subtitle_style))
    if documentos:
        labels_doc = [('nome', 'Nome'), ('tipo', 'Tipo'), ('data_documento', 'Data'), ('nome_arquivo_original', 'Arquivo'), ('observacao', 'Observacao')]
        for documento in documentos:
            adicionar_tabela_chave_valor(story, documento, labels_doc, cell_style, header_color='#002b5c')
            story.append(Spacer(1, 8))
    else:
        story.append(Paragraph("Nenhum arquivo anexado.", cell_style))

    story.append(Spacer(1, 10))
    story.append(Paragraph(
        f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')} | Usuario: {session.get('username', 'sistema')}",
        ParagraphStyle('FooterProcesso', parent=styles['Normal'], fontName='Helvetica', fontSize=8, alignment=2, textColor=colors.grey)
    ))

    doc.build(story, onFirstPage=add_watermark, onLaterPages=add_watermark)
    buffer.seek(0)
    return buffer


def gerar_pdf_geral_processos(processos):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=54, rightMargin=54, topMargin=110, bottomMargin=54)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'GeralProcessosTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=16,
        leading=22,
        alignment=1,
        spaceAfter=14,
        textColor=colors.HexColor('#1a233a')
    )
    subtitle_style = ParagraphStyle(
        'GeralProcessosSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=14,
        spaceAfter=8,
        textColor=colors.HexColor('#374151')
    )
    cell_style = ParagraphStyle(
        'GeralProcessosCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7,
        leading=9,
        wordWrap='CJK'
    )

    story = []
    logo_path = os.path.join(current_app.root_path, 'static', 'logo_codego.png')
    if os.path.exists(logo_path):
        story.append(Image(logo_path, width=300, height=60, hAlign='CENTER'))
        story.append(Spacer(1, 18))

    story.append(Paragraph("RELATORIO GERAL DE PROCESSOS", title_style))
    story.append(Paragraph(f"Total de processos: {len(processos)}", subtitle_style))
    story.append(Spacer(1, 8))

    resumo_status = {}
    for processo in processos:
        status = valor_pdf(processo.get('status'))
        resumo_status[status] = resumo_status.get(status, 0) + 1

    if resumo_status:
        resumo_linhas = [["Status", "Quantidade"]]
        for status, quantidade in sorted(resumo_status.items()):
            resumo_linhas.append([Paragraph(status, cell_style), Paragraph(str(quantidade), cell_style)])

        resumo_table = Table(resumo_linhas, colWidths=[300, 100], repeatRows=1)
        resumo_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a233a')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('FONTSIZE', (0, 1), (-1, -1), 7),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(resumo_table)
        story.append(Spacer(1, 16))

    linhas = [["CNJ", "Titulo", "Tipo", "Tribunal", "Comarca", "Status", "Fase"]]
    for processo in processos:
        linhas.append([
            Paragraph(valor_pdf(processo.get('numero_processo')), cell_style),
            Paragraph(valor_pdf(processo.get('titulo')), cell_style),
            Paragraph(valor_pdf(processo.get('tipo_acao') or processo.get('tipo_processo')), cell_style),
            Paragraph(valor_pdf(processo.get('tribunal')), cell_style),
            Paragraph(valor_pdf(processo.get('comarca')), cell_style),
            Paragraph(valor_pdf(processo.get('status')), cell_style),
            Paragraph(valor_pdf(processo.get('fase')), cell_style),
        ])

    tabela = Table(linhas, colWidths=[82, 95, 80, 75, 65, 55, 58], repeatRows=1)
    tabela.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#7f1d1d')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 7),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 6.5),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.grey),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(tabela)

    story.append(Spacer(1, 10))
    story.append(Paragraph(
        f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')} | Usuario: {session.get('username', 'sistema')}",
        ParagraphStyle('FooterGeralProcessos', parent=styles['Normal'], fontName='Helvetica', fontSize=8, alignment=2, textColor=colors.grey)
    ))

    doc.build(story, onFirstPage=add_watermark, onLaterPages=add_watermark)
    buffer.seek(0)
    return buffer


@relatorio_bp.route('/relatorio', methods=['GET', 'POST'])
@role_required('assent', 'jur', 'admin', 'assent_gestor', 'jur_gestor')
def relatorios():
    role = session.get('role')
    modo = request.args.get('modo')

    if not modo:
        modo = 'jur' if role in ('jur', 'jur_gestor') else 'assent'

    if request.method == 'POST':
        if modo == 'jur':
            relatorio_tipo = request.form.get('relatorio_tipo', 'processo')

            if relatorio_tipo == 'geral_processos':
                try:
                    with get_db() as db:
                        garantir_schema_juridico(db)
                        with db.cursor(dictionary=True) as cursor:
                            cursor.execute("""
                                SELECT id, numero_processo, titulo, descricao, tipo_acao, tipo_processo,
                                       tribunal, vara, comarca, valor_da_causa, status, fase,
                                       data_criacao, assunto_judicial, recurso_acionado, tipo_recurso
                                FROM processos
                                ORDER BY numero_processo
                            """)
                            processos = cursor.fetchall()

                    buffer = gerar_pdf_geral_processos(processos)
                    response = make_response(buffer.getvalue())
                    response.headers['Content-Type'] = 'application/pdf'
                    response.headers['Content-Disposition'] = 'inline; filename="relatorio_geral_processos.pdf"'
                    return response
                except Exception as e:
                    return f"Erro PDF: {e}"

            processo_id = request.form.get('processo')
            if not processo_id:
                flash("Selecione um processo.", "warning")
                return redirect(url_for('relatorio.relatorios', modo=modo))

            try:
                with get_db() as db:
                    garantir_schema_juridico(db)
                    with db.cursor(dictionary=True) as cursor:
                        cursor.execute("""
                            SELECT id, numero_processo, titulo, descricao, tipo_acao, tipo_processo,
                                   tribunal, vara, comarca, valor_da_causa, status, fase,
                                   data_criacao, assunto_judicial, recurso_acionado, tipo_recurso
                            FROM processos
                            WHERE id = %s
                        """, (int(processo_id),))
                        processo = cursor.fetchone()

                        if not processo:
                            flash("Processo nao encontrado.", "warning")
                            return redirect(url_for('relatorio.relatorios', modo=modo))

                        cursor.execute("SELECT * FROM processo_partes WHERE processo_id = %s ORDER BY id", (int(processo_id),))
                        partes = cursor.fetchall()
                        cursor.execute("""
                            SELECT *
                            FROM processo_eventos
                            WHERE processo_id = %s
                            ORDER BY COALESCE(data_evento, created_at) DESC, id DESC
                        """, (int(processo_id),))
                        eventos = cursor.fetchall()
                        cursor.execute("""
                            SELECT *
                            FROM processo_documentos
                            WHERE processo_id = %s
                            ORDER BY COALESCE(data_documento, created_at) DESC, id DESC
                        """, (int(processo_id),))
                        documentos = cursor.fetchall()

                buffer = gerar_pdf_processo(processo, partes, eventos, documentos)
                response = make_response(buffer.getvalue())
                response.headers['Content-Type'] = 'application/pdf'
                response.headers['Content-Disposition'] = f'inline; filename="relatorio_processo_{processo_id}.pdf"'
                return response
            except Exception as e:
                return f"Erro PDF: {e}"

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
            campos_disponiveis = {
                chave: valor
                for chave, valor in lot.items()
                if chave != 'id' and chave not in campos_juridicos_legados
            }
            chaves_ordenadas = [chave for chave in RELATORIO_EMPRESA_ORDEM if chave in campos_disponiveis]
            chaves_ordenadas.extend(
                chave for chave in campos_disponiveis.keys()
                if chave not in chaves_ordenadas
            )

            for chave in chaves_ordenadas:
                valor = campos_disponiveis[chave]
                data.append([
                    Paragraph(LABELS.get(chave, str(chave).replace('_', ' ').title()), cell_style),
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
                'numero_processo': 'Numero do Processo',
                'tipo_processo': 'Tipo de Processo',
                'status': 'Status',
                'assunto_judicial': 'Assunto Judicial',
                'valor_da_causa': 'Valor da Causa',
                'recurso_acionado': 'Recurso Acionado',
                'tipo_recurso': 'Tipo de Recurso',
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

    if modo == 'jur':
        processos = []
        try:
            with get_db() as db:
                garantir_schema_juridico(db)
                with db.cursor(dictionary=True) as cursor:
                    cursor.execute("""
                        SELECT id, numero_processo, titulo, tipo_acao, tribunal, comarca, status, fase
                        FROM processos
                        ORDER BY numero_processo
                    """)
                    processos = cursor.fetchall()
        except Exception as err:
            print("Erro ao carregar processos para relatorio juridico:", err)

        return render_template('relatorios_jur.html', processos=processos)

    empresas = []
    empresas_info = {}

    try:
        with get_db() as db:
            with db.cursor(dictionary=True) as cursor:
                cursor.execute("""
                    SELECT
                        ml.id,
                        ml.municipio,
                        ml.empresa,
                        ml.cnpj,
                        ml.processo_sei,
                        COALESCE(proc.numeros_processos, '') AS numeros_processos
                    FROM municipal_lots ml
                    LEFT JOIN (
                        SELECT empresa_id, GROUP_CONCAT(numero_processo SEPARATOR ' ') AS numeros_processos
                        FROM processos
                        GROUP BY empresa_id
                    ) proc ON proc.empresa_id = ml.id
                    WHERE ml.empresa != '-'
                    ORDER BY ml.empresa
                """)
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

    return render_template('relatorios.html', empresas=empresas, empresas_info=empresas_info)
