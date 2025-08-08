from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import smtplib
from email.message import EmailMessage

def send_to_printer(user_id, session):
    filename = f"/tmp/pedido_{user_id}.pdf"
    c = canvas.Canvas(filename, pagesize=A4)
    c.drawString(100, 800, f"Nombre: {session.get('step_0')}")
    c.drawString(100, 780, f"Hora de recogida: {session.get('step_1')}")
    c.drawString(100, 760, f"Pedido: {session.get('step_2')}")
    c.drawString(100, 740, f"Precio: 25€")
    c.save()

    msg = EmailMessage()
    msg["Subject"] = "Nuevo pedido"
    msg["From"] = "EMAIL_USER"
    msg["To"] = "PRINTER_EMAIL"
    msg.set_content("Pedido generado automáticamente")
    with open(filename, "rb") as f:
        msg.add_attachment(f.read(), maintype="application", subtype="pdf", filename=filename)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login("EMAIL_USER", "EMAIL_PASS")
        smtp.send_message(msg)