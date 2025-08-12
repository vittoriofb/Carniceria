import os
import logging
import base64
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition

def enviar_correo(ruta_ticket, session):
    """
    Envía el ticket por correo usando SendGrid.
    """
    try:
        # Leer variables de entorno
        SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
        REMITENTE = os.getenv("EMAIL_REMITENTE")
        DESTINATARIO = os.getenv("EMAIL_DESTINO")

        # Validaciones
        if not SENDGRID_API_KEY:
            logging.error("❌ Falta la variable de entorno SENDGRID_API_KEY en Render.")
            return
        if not REMITENTE:
            logging.error("❌ Falta la variable de entorno EMAIL_REMITENTE en Render.")
            return
        if not DESTINATARIO:
            logging.error("❌ Falta la variable de entorno EMAIL_DESTINO en Render.")
            return

        # Crear el mensaje
        asunto = "Ticket de tu pedido en Carnicería"
        contenido = f"Hola,\n\nAdjuntamos el ticket de tu pedido:\n\n{session}\n\n¡Gracias por tu compra!"
        message = Mail(
            from_email=REMITENTE,
            to_emails=DESTINATARIO,
            subject=asunto,
            plain_text_content=contenido
        )

        # Adjuntar el archivo del ticket
        if ruta_ticket and os.path.exists(ruta_ticket):
            with open(ruta_ticket, "rb") as f:
                data = f.read()
                encoded_file = base64.b64encode(data).decode()

            attachment = Attachment()
            attachment.file_content = FileContent(encoded_file)
            attachment.file_type = FileType("application/pdf")  # O "text/plain" si no es PDF
            attachment.file_name = FileName(os.path.basename(ruta_ticket))
            attachment.disposition = Disposition("attachment")
            message.attachment = attachment

        # Enviar el correo
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)

        logging.info(f"✅ Correo enviado. Status: {response.status_code}")

    except Exception as e:
        logging.exception("❌ Error enviando correo con SendGrid")
