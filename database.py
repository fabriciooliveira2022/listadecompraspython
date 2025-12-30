import pyodbc

# Configurações do SQL Server
SERVER = r"DESKTOP-URUJPEC\SQLEXPRESS"  # Exemplo: "DESKTOP-URUJPEC\SQLEXPRESS"
DATABASE = "listadecompras"
DRIVER = "ODBC Driver 17 for SQL Server"

def get_connection():
    """
    Retorna uma conexão com o banco SQL Server usando Trusted Connection.
    """
    conn = pyodbc.connect(
        f"DRIVER={{{DRIVER}}};"
        f"SERVER={SERVER};"
        f"DATABASE={DATABASE};"
        f"Trusted_Connection=yes;"
    )
    return conn