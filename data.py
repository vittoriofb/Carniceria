# data.py
import pandas as pd

def cargar_productos(ruta_excel: str = "productos_aranda.xlsx") -> list[str]:
    """
    Carga solo los nombres de los productos desde un Excel con columna 'Nombre'
    """
    df = pd.read_excel(ruta_excel)
    # Convertir a lista normal, todo en minúsculas y limpio
    productos = df["Nombre"].str.lower().str.strip().tolist()
    return productos

# Para uso directo
PRODUCTOS_DB = cargar_productos()
