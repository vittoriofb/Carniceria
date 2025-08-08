from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import smtplib
from email.message import EmailMessage

def send_to_printer(user_id, session):
    filename = f"/tmp/pedido_{user_id}.pdf"
    c = canvas.Canvas(filename, pagesize=A4)

    y = 800  # Posición inicial vertical

    # Datos del cliente
    nombre = session.get("nombre", "Cliente")
    hora = session.get("hora", "No especificada")
    c.drawString(100, y, f"Nombre: {nombre}")
    y -= 20
    c.drawString(100, y, f"Hora de recogida: {hora}")
    y -= 30

    # Si es receta especial, imprimir título
    receta_nombre = session.get("receta_nombre")
    if receta_nombre:
        receta_texto = receta_nombre.capitalize()
        personas = session.get("personas", "?")
        c.drawString(100, y, f"Receta especial: {receta_texto} para {personas} personas")
        y -= 30

    # Pedido
    c.drawString(100, y, "Detalle del pedido:")
    y -= 20
    for linea in session.get("detalle_pedido", []):
        if y < 100:
            c.showPage()
            y = 800
        c.drawString(120, y, linea)
        y -= 20

    # Total
    y -= 20
    total = session.get("total", 0)
    c.drawString(100, y, f"Total: {total:.2f} €")

    y -= 40
    c.drawString(100, y, "¡Gracias por tu compra!")
    c.save()

    # Preparar el email
    msg = EmailMessage()
    msg["Subject"] = "Nuevo pedido"
    msg["From"] = "EMAIL_USER"
    msg["To"] = "PRINTER_EMAIL"
    msg.set_content("Pedido generado automáticamente")

    with open(filename, "rb") as f:
        msg.add_attachment(f.read(), maintype="application", subtype="pdf", filename=filename)

    # Enviar por SMTP
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login("EMAIL_USER", "EMAIL_PASS")
        smtp.send_message(msg)
