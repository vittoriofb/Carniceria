import os
import logging
import base64
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition
from data import PRODUCTOS_DB

def send_to_printer(user_id, session):
    """
    Simula el envío del ticket a la impresora y al correo electrónico.
    """
    try:
        # Generar ticket en formato texto
        ticket_path = generar_ticket(user_id, session)

        # Enviar por correo
        enviar_correo(ticket_path, session)

    except Exception:
        logging.exception("Error en send_to_printer")

def generar_ticket(user_id, session):
    """
    Genera un ticket de compra en un archivo de texto y devuelve la ruta.
    """
    ticket_text = []
    ticket_text.append("=== CARNICERÍA EL BUEN CORTE ===")
    ticket_text.append(f"Cliente: {session.get('nombre', user_id)}")
    ticket_text.append("")

    total = 0
    carrito = session.get("carrito", {})
    for producto, kilos in carrito.items():
        precio_unitario = PRODUCTOS_DB.get(producto, 0)
        subtotal = precio_unitario * kilos
        total += subtotal
        ticket_text.append(f"{producto.capitalize():<10} {kilos:.2f} kg  {precio_unitario:.2f} €/kg  -> {subtotal:.2f} €")

    ticket_text.append("")
    ticket_text.append(f"TOTAL: {total:.2f} €")
    ticket_text.append(f"Hora recogida: {session.get('hora', 'No indicada')}")
    ticket_text.append("================================")
    ticket_text.append("¡Gracias por su compra!")

    ruta_ticket = f"/tmp/ticket_{user_id}.txt"
    with open(ruta_ticket, "w", encoding="utf-8") as f:
        f.write("\n".join(ticket_text))

    return ruta_ticket

def enviar_correo(ruta_ticket, session):
    """
    Envía el ticket por correo usando SendGrid.
    Lee las credenciales desde variables de entorno.
    """
    try:
        SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
        DESTINATARIO = os.getenv("EMAIL_DESTINO", "vbavierita@gmail.com")
        REMITENTE = os.getenv("EMAIL_REMITENTE", "patatavfb6@gmail.com")

        if not SENDGRID_API_KEY:
            logging.error("Falta la variable de entorno SENDGRID_API_KEY")
            return

        asunto = "Ticket de compra - Carnicería El Buen Corte"
        cuerpo = "Adjunto encontrará su ticket de compra. ¡Gracias por confiar en nosotros!"

        message = Mail(
            from_email=REMITENTE,
            to_emails=DESTINATARIO,
            subject=asunto,
            plain_text_content=cuerpo
        )

        # Adjuntar ticket
        with open(ruta_ticket, "rb") as f:
            data = f.read()
            encoded_file = base64.b64encode(data).decode()

        attached_file = Attachment(
            FileContent(encoded_file),
            FileName(os.path.basename(ruta_ticket)),
            FileType("text/plain"),
            Disposition("attachment")
        )

        message.attachment = attached_file

        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)

        logging.info(f"Correo enviado: Status {response.status_code}")

    except Exception:
        logging.exception("Error enviando correo con SendGrid")
