import os
import base64
import logging
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition

def send_to_printer(user_id, session):
    """
    Simula el envío a una impresora y envía el ticket por correo.
    """
    try:
        # Crear ticket en texto simple
        ticket_content = f"Pedido de {session.get('nombre', 'Cliente')}\n"
        ticket_content += f"Hora de recogida: {session.get('hora', 'No indicada')}\n"
        ticket_content += "\nProductos:\n"
        for prod, cant in session.get("carrito", {}).items():
            ticket_content += f"- {prod}: {cant} kg\n"
        ticket_content += f"\nTotal: {session.get('total', 0):.2f} €\n"

        # Guardar ticket en un archivo temporal
        ruta_ticket = "/tmp/pedido.txt"
        with open(ruta_ticket, "w", encoding="utf-8") as f:
            f.write(ticket_content)

        logging.info("Ticket generado correctamente.")

        # Enviar por correo
        enviar_correo(ruta_ticket, session)

    except Exception:
        logging.exception("Error en send_to_printer")


def enviar_correo(ruta_ticket, session):
    """
    Envía el ticket por correo usando SendGrid.
    """
    try:
        SENDGRID_API_KEY = os.getenv("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")
        DESTINATARIO = os.getenv("patatavfb6@gmail.com", "vbavierita@gmail.com")
        REMITENTE = os.getenv("vbavierita@gmail.com", "noreply@carniceria.com")

        if not SENDGRID_API_KEY:
            logging.error("Falta la variable de entorno SENDGRID_API_KEY")
            return

        # Crear mensaje
        message = Mail(
            from_email=REMITENTE,
            to_emails=DESTINATARIO,
            subject="Nuevo pedido de carnicería",
            plain_text_content="Adjunto el ticket de tu pedido."
        )

        # Adjuntar archivo
        with open(ruta_ticket, "rb") as f:
            data = f.read()
            encoded_file = base64.b64encode(data).decode()

        attachment = Attachment()
        attachment.file_content = FileContent(encoded_file)
        attachment.file_type = FileType('text/plain')
        attachment.file_name = FileName('pedido.txt')
        attachment.disposition = Disposition('attachment')

        message.attachment = attachment

        # Enviar
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)

        logging.info(f"Correo enviado. Status code: {response.status_code}")

    except Exception:
        logging.exception("Error enviando correo con SendGrid")
