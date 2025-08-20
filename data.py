# data.py
import pandas as pd

def cargar_productos(ruta_excel: str = "productos_aranda.xlsx") -> dict[str, str]:
    """
    Carga los productos y sus categorías desde un Excel con columnas 'Nombre' y 'Categorias'
    Devuelve: {"pollo": "aves", "paella": "otro", ...}
    """
    df = pd.read_excel(ruta_excel)

    productos = {
        str(row["Nombre"]).lower().strip(): str(row["Categorías"]).lower().strip()
        for _, row in df.iterrows()
    }
    return productos

# Para uso directo
PRODUCTOS_DB = cargar_productos()
