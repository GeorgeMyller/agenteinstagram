import os
from pathlib import Path

def create_optimized_codebase_copy(root_dir, output_file, valid_extensions=None, excluded_patterns=None):
    """
    Cria arquivo TXT com filtros inteligentes para redução de tamanho.
    """
    if valid_extensions is None:
        valid_extensions = ['.md',]
    
    if excluded_patterns is None:
        excluded_patterns = [
            'test_', 'mock_', 'example',  # Ignora arquivos de teste
            'node_modules', '.git',         # Ignora diretórios
            'package-lock.json', 'yarn.lock',# Ignora arquivos de lock
            '.venv'                         # Ignora a pasta do ambiente virtual
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
                    file_path.stat().st_size > 512 * 1024):  # Ignora arquivos > 512KB
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