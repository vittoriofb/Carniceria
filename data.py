# data.py
import pandas as pd

def cargar_productos(ruta_excel: str = "productos_aranda.xlsx") -> dict[str, float]:
    """
    Carga los productos desde un Excel en formato:
    | Producto | Precio |
    """
    df = pd.read_excel(ruta_excel)

    # Normalizamos nombres en minúsculas
    productos = dict(zip(df["Nombre"].str.lower().str.strip()))
    return productos

# Para uso directo
PRODUCTOS_DB = cargar_productos()
