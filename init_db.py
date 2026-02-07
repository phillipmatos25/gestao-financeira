import sqlite3
from werkzeug.security import generate_password_hash

# gera o hash da nova senha
nova_senha = "123456"
senha_hash = generate_password_hash(nova_senha)

# conecta no banco
conn = sqlite3.connect("database.db")
cursor = conn.cursor()

# atualiza a senha do usuário
cursor.execute(
    """
    UPDATE usuarios
    SET senha = ?
    WHERE username = ?
    """,
    (senha_hash, "phillip")  # ajuste o username
)

conn.commit()
conn.close()

print("Senha atualizada com sucesso!")