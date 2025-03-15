import os
import shutil
import sys
import glob
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def cleanup_cache():
    """Limpa todos os arquivos de cache Python"""
    try:
        # Limpa __pycache__ directories
        for pycache in glob.glob("**/__pycache__", recursive=True):
            shutil.rmtree(pycache)
            logger.info(f"Removido diretório de cache: {pycache}")

        # Limpa .pyc files
        for pyc in glob.glob("**/*.pyc", recursive=True):
            os.remove(pyc)
            logger.info(f"Removido arquivo .pyc: {pyc}")

        # Limpa .pyo files
        for pyo in glob.glob("**/*.pyo", recursive=True):
            os.remove(pyo)
            logger.info(f"Removido arquivo .pyo: {pyo}")

    except Exception as e:
        logger.error(f"Erro ao limpar cache: {str(e)}")

def cleanup_temp_files():
    """Limpa arquivos temporários que podem ter sido criados"""
    try:
        # Limpa arquivos .tmp
        for tmp in glob.glob("**/*.tmp", recursive=True):
            os.remove(tmp)
            logger.info(f"Removido arquivo temporário: {tmp}")

        # Limpa arquivos de log antigos
        for log in glob.glob("**/*.log", recursive=True):
            os.remove(log)
            logger.info(f"Removido arquivo de log: {log}")

    except Exception as e:
        logger.error(f"Erro ao limpar arquivos temporários: {str(e)}")

def reset_websocket_manager():
    """Reseta o arquivo do WebSocket manager para garantir estado limpo"""
    try:
        # Backup do arquivo original
        if os.path.exists("websocket_manager.py"):
            shutil.copy2("websocket_manager.py", "websocket_manager.py.bak")
            logger.info("Backup do websocket_manager.py criado")

    except Exception as e:
        logger.error(f"Erro ao fazer backup do websocket_manager: {str(e)}")

if __name__ == "__main__":
    logger.info("Iniciando limpeza...")
    
    cleanup_cache()
    cleanup_temp_files()
    reset_websocket_manager()
    
    logger.info("Limpeza concluída!") 