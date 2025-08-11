from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import os
import logging

def send_to_printer(user_id, session):
    """
    Genera un PDF con el pedido y lo envía por correo usando SendGrid.
    """
    try:
        filename = f"/tmp/pedido_{user_id}.pdf"
        c = canvas.Canvas(filename, pagesize=A4)

        y = 800
        nombre = session.get("nombre", "Cliente")
        hora = session.get("hora", "No especificada")
        c.drawString(100, y, f"Nombre: {nombre}")
        y -= 20
        c.drawString(100, y, f"Hora de recogida: {hora}")
        y -= 30

        if "producto" in session:
            c.drawString(100, y, f"Producto: {session['producto']}")
            y -= 20
        if "cantidad" in session:
            c.drawString(100, y, f"Cantidad: {session['cantidad']} kg")
            y -= 20
        if "total" in session:
            c.drawString(100, y, f"Total: {session['total']:.2f} €")
            y -= 30

        c.save()

        enviar_correo(
            destinatario="patatavfb6@gmail.com",  # Cambiar por destino real
            asunto="Tu pedido en la carnicería",
            contenido="Adjunto encontrarás tu ticket en PDF.",
            archivo=filename
        )

    except Exception as e:
        logging.exception("Error generando o enviando el ticket")


def enviar_correo(destinatario, asunto, contenido, archivo=None):
    """
    Envía un correo usando SendGrid con adjunto opcional.
    """
    try:
        message = Mail(
            from_email="vbavierita@gmail.com",
            to_emails=destinatario,
            subject=asunto,
            html_content=contenido
        )

        if archivo and os.path.exists(archivo):
            with open(archivo, "rb") as f:
                import base64
                message.add_attachment(
                    base64.b64encode(f.read()).decode(),
                    "application/pdf",
                    os.path.basename(archivo),
                    "attachment"
                )

        sg = SendGridAPIClient(os.environ.get('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
'))
        sg.send(message)
        logging.info(f"Correo enviado a {destinatario}")

    except Exception as e:
        logging.exception("Error enviando correo con SendGrid")
