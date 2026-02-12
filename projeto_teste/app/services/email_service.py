import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app

def enviar_email(destinatario, assunto, corpo):
    smtp_server = current_app.config['SMTP_SERVER']
    smtp_port = current_app.config['SMTP_PORT']
    smtp_username = current_app.config['SMTP_USER']
    smtp_password = current_app.config['SMTP_PASS']

    msg = MIMEMultipart()
    msg['From'] = smtp_username
    msg['To'] = destinatario
    msg['Subject'] = assunto

    msg.attach(MIMEText(corpo, 'plain', 'utf-8'))

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_username, smtp_password)
        server.sendmail(smtp_username, [destinatario], msg.as_string())
        server.quit()

        return True
    
    except Exception as e:
        current_app.logger.error(f"Erro ao enviar email: {str(e)}")
        return False