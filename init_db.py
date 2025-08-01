import sqlite3

def deletar_movimentacao(id_para_deletar):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM movimentacoes WHERE id = ?", (id_para_deletar,))
    conn.commit()
    conn.close()
    print(f"Registro com id={id_para_deletar} deletado com sucesso.")

if __name__ == "__main__":
    deletar_movimentacao(187)