#!/usr/bin/env python
"""
Script to create a basic border image for Instagram carousel posts.
This creates a simple white border with a transparent center.
"""

# Este arquivo cria uma imagem de borda personalizada para ser usada nas postagens do Instagram

# Importando as bibliotecas necessárias
import os  # Para operações com arquivos e diretórios
from PIL import Image, ImageDraw  # Para criar e manipular imagens
from src.utils.paths import Paths  # Para gerenciar caminhos de arquivos do projeto

def create_border_image(width=1080, height=1350):
    """
    Cria uma imagem de borda transparente com um retângulo branco
    
    Args:
        width (int): Largura da imagem (padrão: 1080px - tamanho recomendado para Instagram)
        height (int): Altura da imagem (padrão: 1350px - proporção 4:5 do Instagram)
    
    Returns:
        str: Caminho do arquivo da imagem de borda criada
    """
    try:
        # Cria uma nova imagem com canal alpha (transparência)
        image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        
        # Cria um objeto para desenhar na imagem
        draw = ImageDraw.Draw(image)
        
        # Define a espessura da borda
        border_width = 10
        
        # Desenha um retângulo branco com a espessura definida
        draw.rectangle(
            [(0, 0), (width, height)],  # Coordenadas do retângulo (toda a imagem)
            outline=(255, 255, 255, 255),  # Cor branca com 100% de opacidade
            width=border_width  # Espessura da linha
        )
        
        # Cria o diretório assets se não existir
        os.makedirs(Paths.ASSETS_DIR, exist_ok=True)
        
        # Define o caminho onde a imagem será salva
        border_path = os.path.join(Paths.ASSETS_DIR, "moldura.png")
        
        # Salva a imagem
        image.save(border_path, "PNG")
        
        print(f"✅ Imagem de borda criada em: {border_path}")
        return border_path
        
    except Exception as e:
        print(f"❌ Erro ao criar imagem de borda: {str(e)}")
        return None

if __name__ == "__main__":
    # Se este arquivo for executado diretamente, cria a imagem de borda
    create_border_image()
