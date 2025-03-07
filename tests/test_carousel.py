import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.instagram.carousel_poster import upload_carousel_images
from src.instagram.instagram_carousel_service import InstagramCarouselService

def test_carousel():
    """
    Testa a publicação de um carrossel usando as imagens de teste
    """
    print("Iniciando teste de carrossel")
    
    # Diretório atual do script
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Arquivos de teste
    test_images = [
        os.path.join(current_dir, "test_image1.jpg"),
        os.path.join(current_dir, "test_image2.jpg")
    ]
    
    # Verificar se os arquivos existem
    missing_files = [img for img in test_images if not os.path.exists(img)]
    if missing_files:
        print(f"ERRO: Arquivos de teste não encontrados: {missing_files}")
        print("Por favor, crie arquivos de teste com nomes 'test_image1.jpg' e 'test_image2.jpg' na pasta 'tests'")
        return False
    
    # 1. Fazer upload das imagens
    print("Fazendo upload das imagens de teste...")
    success, uploaded_images, image_urls = upload_carousel_images(test_images)
    
    if not success or len(image_urls) != 2:
        print(f"ERRO: Falha no upload das imagens. URLs obtidas: {image_urls}")
        return False
    
    print(f"Upload concluído com sucesso. URLs: {image_urls}")
    
    # 2. Criar o serviço do Instagram
    print("Criando serviço do Instagram...")
    service = InstagramCarouselService()
    
    # 3. Publicar o carrossel
    print("Publicando carrossel...")
    caption = "Teste de carrossel - por favor ignore"
    post_id = service.post_carousel(image_urls, caption)
    
    if not post_id:
        print("ERRO: Falha ao publicar o carrossel")
        return False
    
    print(f"Carrossel publicado com sucesso! ID: {post_id}")
    return True

if __name__ == "__main__":
    if test_carousel():
        print("Teste concluído com sucesso!")
        exit(0)
    else:
        print("Teste falhou")
        exit(1)