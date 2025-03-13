import pandas as pd

# Ler o arquivo Excel
file_path = "C:\Users\julio\Downloads\LISTAS INDIVIDUAIS.xlsx"
df = pd.read_excel(file_path, engine='openpyxl')

# Limpar os dados
df['Nome'] = df['Nome'].str.strip()
df = df.drop_duplicates(subset='Nome')

# Criar um dicionário
dicionario_colaboradores = {row['Nome']: {'Função': row.get('Função', 'N/A'), 'Meta': row.get('Meta', 0)} for _, row in df.iterrows()}

# Salvar backup
backup_file = "colaboradores_backup.json"
with open(backup_file, 'w', encoding='utf-8') as f:
    import json
    json.dump(dicionario_colaboradores, f, ensure_ascii=False, indent=4)

print("Dados organizados e backup salvo!")