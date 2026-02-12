import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from flask import current_app

def add_watermark(canvas, doc):
    canvas.saveState()
    logo_path = os.path.join(current_app.root_path, 'static', 'logo_codego_grey.png')
    if os.path.exists(logo_path):
        logo = ImageReader(logo_path)
        page_width, page_height = A4
        iw, ih = logo.getSize()
        scale = 600 / iw
        width = 600
        height = ih * scale

        canvas.translate(page_width / 2, page_height / 2)
        canvas.rotate(45)
        canvas.setFillAlpha(0.08)
        canvas.drawImage(logo, -width/2, -height/2, width=width, height=height, mask='auto')
        canvas.setFillAlpha(1.0)
    canvas.restoreState()
