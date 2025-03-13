import unittest
from pathlib import Path
import pandas as pd
import numpy as np
from analisar_dados_v5 import AnalisadorInteligente
import os
import sqlite3
import requests
import time

class TestAnalisadorInteligente(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Setup inicial que roda uma vez antes de todos os testes"""
        cls.analisador = AnalisadorInteligente()
        cls.workspace_dir = Path('F:/relatoriotest')
        
    def setUp(self):
        """Setup que roda antes de cada teste individual"""
        self.arquivos_requeridos = [
            '(JULIO) LISTAS INDIVIDUAIS.xlsx',
            '(LEANDRO_ADRIANO) LISTAS INDIVIDUAIS.xlsx'
        ]
        
    def test_01_verificar_diretorios(self):
        """Testa se os diretórios necessários existem"""
        print("\nTestando diretórios...")
        for diretorio in self.analisador.diretorios:
            with self.subTest(diretorio=diretorio):
                self.assertTrue(
                    Path(diretorio).exists(),
                    f"Diretório {diretorio} não encontrado"
                )
    
    def test_02_verificar_arquivos_excel(self):
        """Testa se os arquivos Excel necessários existem"""
        print("\nTestando arquivos Excel...")
        for arquivo in self.arquivos_requeridos:
            caminho = self.workspace_dir / arquivo
            with self.subTest(arquivo=arquivo):
                self.assertTrue(
                    caminho.exists(),
                    f"Arquivo {arquivo} não encontrado"
                )
                self.assertTrue(
                    caminho.stat().st_size > 0,
                    f"Arquivo {arquivo} está vazio"
                )
    
    def test_03_carregar_dados(self):
        """Testa se é possível carregar os dados dos arquivos Excel"""
        print("\nTestando carregamento de dados...")
        dados_grupos = self.analisador.carregar_dados()
        
        # Verifica se retornou um dicionário
        self.assertIsInstance(dados_grupos, dict)
        
        # Verifica se os grupos esperados estão presentes
        grupos_esperados = ['julio', 'leandro']
        for grupo in grupos_esperados:
            with self.subTest(grupo=grupo):
                self.assertIn(grupo, dados_grupos)
        
        # Verifica estrutura dos dados
        for grupo, dados in dados_grupos.items():
            with self.subTest(grupo=grupo):
                self.assertIn('colaboradores', dados)
                self.assertIn('metricas', dados)
                
                # Verifica se há dados de colaboradores
                self.assertGreater(len(dados['colaboradores']), 0)
                
                # Verifica estrutura das métricas
                for colaborador, metricas in dados['metricas'].items():
                    with self.subTest(colaborador=colaborador):
                        self.assertIn('total_registros', metricas)
                        self.assertIn('status_counts', metricas)
                        self.assertIn('metricas_diarias', metricas)
                        self.assertIn('produtividade_hora', metricas)
    
    def test_04_validar_status(self):
        """Testa a validação dos status nos dados"""
        print("\nTestando validação de status...")
        dados_grupos = self.analisador.carregar_dados()
        
        status_validos = set([
            'VERIFICADO', 'ANÁLISE', 'PENDENTE', 'PRIORIDADE',
            'PRIORIDADE TOTAL', 'APROVADO', 'APREENDIDO', 'CANCELADO',
            'QUITADO', 'OUTROS ACORDOS', 'M.ENCAMINHADA'
        ])
        
        for grupo, dados in dados_grupos.items():
            for colaborador, df in dados['colaboradores'].items():
                if 'STATUS' in df.columns:
                    status_encontrados = set(df['STATUS'].unique())
                    with self.subTest(grupo=grupo, colaborador=colaborador):
                        # Verifica se todos os status encontrados são válidos
                        status_invalidos = status_encontrados - status_validos
                        self.assertEqual(
                            len(status_invalidos), 0,
                            f"Status inválidos encontrados: {status_invalidos}"
                        )
    
    def test_05_calcular_metricas_avancadas(self):
        """Testa o cálculo de métricas avançadas"""
        print("\nTestando cálculo de métricas avançadas...")
        dados_grupos = self.analisador.carregar_dados()
        df_metricas = self.analisador.calcular_metricas_avancadas(dados_grupos)
        
        # Verifica se retornou um DataFrame
        self.assertIsInstance(df_metricas, pd.DataFrame)
        
        # Verifica colunas necessárias
        colunas_requeridas = [
            'grupo', 'colaborador', 'total_registros', 'aprovados',
            'taxa_prioritarios', 'produtividade_hora', 'score_eficiencia'
        ]
        for coluna in colunas_requeridas:
            with self.subTest(coluna=coluna):
                self.assertIn(coluna, df_metricas.columns)
        
        # Verifica se os valores estão dentro dos limites esperados
        self.assertTrue(all(df_metricas['taxa_prioritarios'].between(0, 100)))
        self.assertTrue(all(df_metricas['produtividade_hora'] >= 0))
        self.assertTrue(all(df_metricas['score_eficiencia'] >= 0))
    
    def test_06_gerar_relatorio_txt(self):
        """Testa a geração do relatório em formato TXT"""
        print("\nTestando geração de relatório TXT...")
        dados_grupos = self.analisador.carregar_dados()
        arquivo_saida = self.analisador.gerar_relatorio_txt(dados_grupos)
        
        # Verifica se o arquivo foi criado
        self.assertTrue(arquivo_saida.exists())
        self.assertTrue(arquivo_saida.stat().st_size > 0)
        
        # Verifica conteúdo básico do arquivo
        with open(arquivo_saida, 'r', encoding='utf-8') as f:
            conteudo = f.read()
            self.assertIn("RELATÓRIO COMPLETO DE ANÁLISE DE CONTRATOS", conteudo)
            self.assertIn("Data de Geração:", conteudo)
    
    def test_07_exportar_sqlite(self):
        """Testa a exportação para SQLite"""
        print("\nTestando exportação para SQLite...")
        resultado = self.analisador.exportar_para_sqlite()
        self.assertTrue(resultado)
        
        # Verifica se o banco de dados foi criado
        db_path = self.workspace_dir / 'relatorio_dashboard.db'
        self.assertTrue(db_path.exists())
        
        # Verifica se as tabelas foram criadas
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Lista todas as tabelas
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tabelas = cursor.fetchall()
        tabelas = [t[0] for t in tabelas]
        
        tabelas_esperadas = ['grupos', 'colaboradores', 'relatorio_geral', 'metricas_produtividade']
        for tabela in tabelas_esperadas:
            with self.subTest(tabela=tabela):
                self.assertIn(tabela, tabelas)
        
        conn.close()

    def test_08_verificar_servidor_e_dados(self):
        """Testa o funcionamento do servidor e a extração de dados do DB"""
        print("\nTestando servidor e extração de dados...")
        
        # Verificar se o servidor está rodando
        max_tentativas = 3
        tentativa = 0
        servidor_online = False
        
        while tentativa < max_tentativas and not servidor_online:
            try:
                response = requests.get('http://localhost:8000/status')
                if response.status_code == 200:
                    servidor_online = True
                    print("✓ Servidor está online")
                else:
                    print(f"Tentativa {tentativa + 1}: Servidor retornou status {response.status_code}")
                    time.sleep(2)  # Esperar 2 segundos antes da próxima tentativa
            except requests.exceptions.ConnectionError:
                print(f"Tentativa {tentativa + 1}: Servidor não está respondendo")
                time.sleep(2)
            tentativa += 1
        
        self.assertTrue(servidor_online, "Servidor não está funcionando corretamente")
        
        # Verificar conexão com o banco de dados
        db_path = self.workspace_dir / 'relatorio_dashboard.db'
        self.assertTrue(db_path.exists(), "Banco de dados não encontrado")
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Verificar tabelas necessárias
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tabelas = {row[0] for row in cursor.fetchall()}
            tabelas_necessarias = {'grupos', 'colaboradores', 'relatorio_geral', 'metricas_produtividade'}
            
            self.assertTrue(
                tabelas_necessarias.issubset(tabelas),
                f"Tabelas faltando: {tabelas_necessarias - tabelas}"
            )
            
            # Verificar se há dados nas tabelas
            for tabela in tabelas_necessarias:
                cursor.execute(f"SELECT COUNT(*) FROM {tabela}")
                count = cursor.fetchone()[0]
                self.assertGreater(
                    count, 0,
                    f"Tabela {tabela} está vazia"
                )
            
            print("✓ Banco de dados está configurado corretamente")
            conn.close()
            
        except sqlite3.Error as e:
            self.fail(f"Erro ao acessar banco de dados: {str(e)}")

if __name__ == '__main__':
    # Configurar o formato de saída dos testes
    unittest.main(verbosity=2) 