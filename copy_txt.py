'''import os
from pathlib import Path

def create_codebase_copy(root_dir, output_file, valid_extensions=None, excluded_dirs=None):
    """
    Cria uma cópia formatada da codebase em um arquivo de texto.
    
    Args:
        root_dir (str): Diretório raiz para iniciar a busca
        output_file (str): Nome do arquivo de saída
        valid_extensions (list): Extensões de arquivo para incluir
        excluded_dirs (list): Diretórios para excluir
    """
    if valid_extensions is None:
        valid_extensions = ['.py', '.js', '.java', '.html', '.css', '.php', '.rb', '.c', '.cpp', '.h', '.sql']
    
    if excluded_dirs is None:
        excluded_dirs = ['__pycache__', '.git', 'venv', 'node_modules', '.idea', 'vendor']
    
    header = """
╔══════════════════════════════════════════════════╗
║                CODIGO-FONTE v1.0                 ║
╠══════════════════════════════════════════════════╣
║ Cópia formatada da codebase - Estrutura original ║
╚══════════════════════════════════════════════════╝\n\n
"""
    
    with open(output_file, 'w', encoding='utf-8') as outfile:
        outfile.write(header)
        
        for root, dirs, files in os.walk(root_dir):
            # Remove diretórios excluídos
            dirs[:] = [d for d in dirs if d not in excluded_dirs]
            
            for file in files:
                file_path = Path(root) / file
                ext = file_path.suffix.lower()
                
                if ext in valid_extensions:
                    try:
                        # Cabeçalho do arquivo
                        relative_path = file_path.relative_to(root_dir)
                        separator = f"\n\n{'═' * 80}\n"
                        file_header = f"📁 ARQUIVO: {relative_path}\n{'═' * 80}\n\n"
                        
                        outfile.write(separator)
                        outfile.write(file_header)
                        
                        # Escreve o conteúdo
                        with open(file_path, 'r', encoding='utf-8') as infile:
                            content = infile.read()
                            outfile.write(content)
                            outfile.write("\n\n")
                            
                    except UnicodeDecodeError:
                        print(f"⚠️ Erro de decodificação em: {file_path} (arquivo ignorado)")
                    except Exception as e:
                        print(f"⚠️ Erro ao processar {file_path}: {str(e)}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Cria uma cópia formatada da codebase')
    parser.add_argument('-d', '--dir', default='.', help='Diretório raiz (padrão: diretório atual)')
    parser.add_argument('-o', '--output', default='codebase_copy.txt', help='Arquivo de saída (padrão: codebase_copy.txt)')
    
    args = parser.parse_args()
    
    print(f"🚀 Iniciando cópia da codebase em: {args.dir}")
    create_codebase_copy(args.dir, args.output)
    print(f"✅ Concluído! Arquivo gerado: {args.output}")'''

import os
from pathlib import Path

def create_optimized_codebase_copy(root_dir, output_file, valid_extensions=None, excluded_patterns=None):
    """
    Cria arquivo TXT com filtros inteligentes para redução de tamanho.
    """
    if valid_extensions is None:
        valid_extensions = ['.py', '.js', '.java']
    
    if excluded_patterns is None:
        excluded_patterns = [
            'test_', 'mock_', 'example', # Ignora arquivos de teste
            'node_modules', '.git', # Ignora diretórios
            'package-lock.json', 'yarn.lock' # Ignora arquivos de lock
        ]

    with open(output_file, 'w', encoding='utf-8') as outfile:
        for root, dirs, files in os.walk(root_dir):
            # Filtra diretórios
            dirs[:] = [d for d in dirs if not any(p in d for p in excluded_patterns)]
            
            for file in files:
                file_path = Path(root) / file
                
                # Aplica filtros
                if (file_path.suffix.lower() not in valid_extensions or
                    any(p in file_path.name for p in excluded_patterns) or
                    file_path.stat().st_size > 512 * 1024):  # Ignora > 512KB
                    continue
                
                try:
                    relative_path = file_path.relative_to(root_dir)
                    outfile.write(f"\n║ {'■' * 50}\n║ ▶ {relative_path}\n║ {'■' * 50}\n\n")
                    
                    with open(file_path, 'r', encoding='utf-8') as infile:
                        for line in infile:
                            # Remove linhas vazias e comentários
                            stripped = line.strip()
                            if stripped and not stripped.startswith(('//', '#', '/*')):
                                outfile.write(line)
                            
                except Exception as e:
                    print(f"⚠️ Erro processando {file_path}: {str(e)}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Cria cópia otimizada da codebase')
    parser.add_argument('-d', '--dir', default='.', help='Diretório raiz')
    parser.add_argument('-o', '--output', default='code_light.txt', help='Arquivo de saída')
    
    args = parser.parse_args()
    
    print(f"🚀 Processando: {args.dir}")
    create_optimized_codebase_copy(args.dir, args.output)
    print(f"✅ Concluído! Arquivo otimizado: {args.output}")