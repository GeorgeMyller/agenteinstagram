import os
import time
import requests
import logging
from src.instagram.crew_post_instagram import InstagramPostCrew
from src.instagram.describe_image_tool import ImageDescriber
from src.instagram.instagram_post_service import InstagramPostService
from src.instagram.border import ImageWithBorder
from src.instagram.filter import FilterImage
from src.utils.paths import Paths
from src.instagram.image_uploader import ImageUploader
from PIL import Image

# Import new queue system
from src.services.post_queue import post_queue, RateLimitExceeded
from src.instagram.instagram_post_publisher import PostPublisher
# Import the new carousel normalizer
from src.instagram.carousel_normalizer import CarouselNormalizer

# Set up logging
logger = logging.getLogger('InstagramSend')

class InstagramSend:
    # Keep track of rate limits
    last_rate_limit_time = 0
    rate_limit_window = 3600  # 1 hour window for rate limiting
    max_rate_limit_hits = 52  # Maximum number of rate limit hits before enforcing longer delays
    
    @staticmethod
    def queue_post(image_path, caption, inputs=None) -> str:
        """
        Queue an image to be posted to Instagram asynchronously
        
        Args:
            image_path (str): Path to the image file
            caption (str): Caption text
            inputs (dict): Optional configuration for post generation
            
        Returns:
            str: Job ID for tracking the post status
        """
        # Validate inputs before queuing
        if not caption or caption.lower() == "none":
            caption = "A Acesso IA está transformando processos com IA! 🚀"
            print(f"Caption vazia ou 'None'. Usando caption padrão: '{caption}'")

        # Validate image path
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Arquivo de imagem não encontrado: {image_path}")
            
        # Add to queue and return job ID
        job_id = post_queue.add_job(image_path, caption, inputs)
        return job_id
    
    @staticmethod
    def queue_reels(video_path, caption, inputs=None) -> str:
        """
        Queue a video to be posted to Instagram as a reel asynchronously
        
        Args:
            video_path (str): Path to the video file
            caption (str): Caption text
            inputs (dict): Optional configuration for post generation
            
        Returns:
            str: Job ID for tracking the post status
        """
        # Validate inputs before queuing
        if not caption or caption.lower() == "none":
            caption = "A Acesso IA está transformando processos com IA! 🚀 #reels #ai"
            print(f"Caption vazia ou 'None'. Usando caption padrão para reels: '{caption}'")

        # Validate video path
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Arquivo de vídeo não encontrado: {video_path}")
        
        # We'll add a special flag to indicate this is a video/reel
        if inputs is None:
            inputs = {}
            
        inputs["content_type"] = "reel"
        inputs["video_path"] = video_path
        
        print(f"Caption in queue_reels: {caption}")  # Debug statement
        # Add to queue and return job ID - using the same queue system for now
        # The worker will need to check the content_type to handle differently
        job_id = post_queue.add_job(video_path, caption, inputs)
        print(f"Reel queued with job ID: {job_id}")
        return job_id
    
    @staticmethod
    def queue_carousel(image_paths, caption, inputs=None):
        """
        Enfileira um carrossel de imagens para o Instagram
        
        Args:
            image_paths (list): Lista de caminhos dos arquivos de mídia (imagens)
            caption (str): Legenda do post
            inputs (dict): Configurações adicionais
            
        Returns:
            str: ID do trabalho
        """
        # Adicionar o trabalho à fila de processamento
        if inputs is None:
            inputs = {}
            
        # Add content_type explicitly to mark this as a carousel
        inputs["content_type"] = "carousel"
        
        job_id = post_queue.add_job(image_paths, caption, inputs)
        return job_id

    @staticmethod
    def check_post_status(job_id):
        """
        Check the status of a queued post
        
        Args:
            job_id (str): Job ID returned when queuing the post
            
        Returns:
            dict: Job status information
        """
        return post_queue.get_job_status(job_id)
    
    @staticmethod
    def get_queue_stats():
        """
        Get statistics about the current queue
        
        Returns:
            dict: Queue statistics
        """
        return post_queue.get_queue_stats()
    
    @staticmethod
    def get_recent_posts(limit=10):
        """
        Get recent post history
        
        Args:
            limit (int): Maximum number of posts to return
            
        Returns:
            list: Recent post history
        """
        return post_queue.get_job_history(limit)
    
    @staticmethod
    def send_instagram(image_path, caption, inputs=None):
        """
        Send an image to Instagram with a caption.

        Args:
            image_path (str): Path to the image file
            caption (str): Caption text
            inputs (dict): Optional configuration for post generation
        """
        result = None
        original_image_path = image_path
        uploaded_images = []
        uploader = ImageUploader()  # Reuse the same uploader instance
        
        # Validar caption antes do processamento
        if not caption or caption.lower() == "none":
            caption = "A Acesso IA está transformando processos com IA! 🚀"
            print(f"Caption vazia ou 'None'. Usando caption padrão: '{caption}'")
        
        try:
            if inputs is None:
                inputs = {
                    "estilo": "Divertido, Alegre, Sarcástico e descontraído",
                    "pessoa": "Terceira pessoa do singular",
                    "sentimento": "Positivo",
                    "tamanho": "200 palavras",
                    "genero": "Neutro",
                    "emojs": "sim",
                    "girias": "sim"
                }
            
            # Verificar se o arquivo existe
            if not os.path.exists(image_path):
                raise FileNotFoundError(f"Arquivo de imagem não encontrado: {image_path}")
                
            border_image = os.path.join(Paths.SRC_DIR, "instagram", "moldura.png")
            
            # Process image with filter
            print("Aplicando filtros à imagem...")
            image_path = FilterImage.process(image_path)
            
            # First upload to get image description
            print("Obtendo descrição da imagem...")
            try:
                temp_image = uploader.upload_from_path(image_path)
                uploaded_images.append(temp_image)
                describe = ImageDescriber.describe(temp_image['url'])
                
                # Try to delete the temporary image immediately after getting description
                if temp_image.get("deletehash"):
                    print(f"Deletando imagem temporária usada para descrição...")
                    if uploader.delete_image(temp_image["deletehash"]):
                        uploaded_images.remove(temp_image)
            except Exception as e:
                print(f"Erro ao obter descrição da imagem: {str(e)}")
                describe = "Imagem para publicação no Instagram."
                
            # Add border and prepare final image
            print("Aplicando bordas e filtros...")
            try:
                image = ImageWithBorder.create_bordered_image(
                    border_path=border_image,
                    image_path=image_path,
                    output_path=image_path                
                )
            except Exception as e:
                print(f"Erro ao aplicar borda à imagem: {str(e)}")
                # Continue with original image if border application fails
            
            # Upload final image
            print("Enviando imagem para publicação...")
            try:
                final_image = uploader.upload_from_path(image_path)
                uploaded_images.append(final_image)
            except Exception as e:
                print(f"Erro ao fazer upload da imagem final: {str(e)}")
                raise
            
            # Generate caption
            print("Gerando legenda...")
            try:
                crew = InstagramPostCrew()
                # Usar um dicionário diretamente
                inputs_dict = {
                    "genero": inputs.get('genero', 'Neutro'),
                    "caption": caption,
                    "describe": describe,
                    "estilo": inputs.get('estilo', 'Divertido, Alegre, Sarcástico e descontraído'),
                    "pessoa": inputs.get('pessoa', 'Terceira pessoa do singular'),
                    "sentimento": inputs.get('sentimento', 'Positivo'),
                    "tamanho": inputs.get('tamanho', '200 palavras'),
                    "emojs": inputs.get('emojs', 'sim'),
                    "girias": inputs.get('girias', 'sim')
                }
                final_caption = crew.kickoff(inputs=inputs_dict)  # Passar o dicionário
            except Exception as e:
                print(f"Erro ao gerar legenda: {str(e)}")
                final_caption = caption  # Usar a legenda original em caso de erro
            
            # Adicionar texto padrão ao final da legenda
            final_caption = final_caption + "\n\n-------------------"
            final_caption = final_caption + "\n\n Essa postagem foi toda realizada por um agente inteligente"
            final_caption = final_caption + "\n O agente desempenhou as seguintes ações:"
            final_caption = final_caption + "\n 1 - Idenficação e reconhecimento do ambiente da fotografia"
            final_caption = final_caption + "\n 2 - Aplicação de Filtros de contraste e autocorreção da imagem"
            final_caption = final_caption + "\n 3 - Aplicação de moldura específica"
            final_caption = final_caption + "\n 4 - Definição de uma persona específica com base nas preferências"
            final_caption = final_caption + "\n 5 - Criação da legenda com base na imagem e na persona"
            final_caption = final_caption + "\n 6 - Postagem no feed do instagram"
            final_caption = final_caption + "\n\n-------------------"
            
            # Post to Instagram with enhanced rate limit handling
            print("Iniciando processo de publicação no Instagram...")
            
            try:
                # Verificar limites de requisição
                stats = post_queue.get_queue_stats()
                current_time = time.time()
                
                if stats["rate_limited_posts"] > InstagramSend.max_rate_limit_hits:
                    # Check if we're still within the rate limit window
                    if (current_time - InstagramSend.last_rate_limit_time) < InstagramSend.rate_limit_window:
                        remaining_time = InstagramSend.rate_limit_window - (current_time - InstagramSend.last_rate_limit_time)
                        raise RateLimitExceeded(
                            f"Taxa de requisições severamente excedida. "
                            f"Aguarde {int(remaining_time/60)} minutos antes de tentar novamente."
                        )
                    else:
                        # Reset rate limit tracking if window has passed
                        InstagramSend.last_rate_limit_time = 0
                        stats["rate_limited_posts"] = 0

                # Instanciar o serviço e publicar a foto
                insta_post = InstagramPostService()
                result = insta_post.post_image(final_image['url'], final_caption)
                
                if not result:
                    print(f"Failed to publish photo from {image_path}")
                    return None

                print(f"Photo published successfully! ID: {result.get('id')}")
                return result
            except Exception as e:
                print(f"Error posting to Instagram: {str(e)}")
                import traceback
                print(traceback.format_exc())
                return None

        except Exception as e:
            print(f"Error publishing photo: {e}")
            import traceback
            print(traceback.format_exc())
            return None

    @staticmethod
    def send_instagram_reel(video_path, caption, inputs=None):
        """
        Send a reel to Instagram with a caption.

        Args:
            video_path (str): Path to the video file
            caption (str): Caption text
            inputs (dict): Optional configuration for post generation
        """
        result = None
        original_video_path = video_path
        uploaded_videos = []
        uploader = VideoUploader()  # Reuse the same uploader instance
        
        # Validar caption antes do processamento
        if not caption or caption.lower() == "none":
            caption = "A Acesso IA está transformando processos com IA! 🚀"
            print(f"Caption vazia ou 'None'. Usando caption padrão: '{caption}'")
        
        try:
            if inputs is None:
                inputs = {
                    "estilo": "Divertido, Alegre, Sarcástico e descontraído",
                    "pessoa": "Terceira pessoa do singular",
                    "sentimento": "Positivo",
                    "tamanho": "200 palavras",
                    "genero": "Neutro",
                    "emojs": "sim",
                    "girias": "sim"
                }
            
            # Verificar se o arquivo existe
            if not os.path.exists(video_path):
                raise FileNotFoundError(f"Arquivo de vídeo não encontrado: {video_path}")
                
            # Process video with filter
            print("Aplicando filtros ao vídeo...")
            video_path = FilterVideo.process(video_path)
            
            # First upload to get video description
            print("Obtendo descrição do vídeo...")
            try:
                temp_video = uploader.upload_from_path(video_path)
                uploaded_videos.append(temp_video)
                describe = VideoDescriber.describe(temp_video['url'])
                
                # Try to delete the temporary video immediately after getting description
                if temp_video.get("deletehash"):
                    print(f"Deletando vídeo temporário usado para descrição...")
                    if uploader.delete_video(temp_video["deletehash"]):
                        uploaded_videos.remove(temp_video)
            except Exception as e:
                print(f"Erro ao obter descrição do vídeo: {str(e)}")
                describe = "Vídeo para publicação no Instagram."
                
            # Upload final video
            print("Enviando vídeo para publicação...")
            try:
                final_video = uploader.upload_from_path(video_path)
                uploaded_videos.append(final_video)
            except Exception as e:
                print(f"Erro ao fazer upload do vídeo final: {str(e)}")
                raise
            
            # Generate caption
            print("Gerando legenda...")
            try:
                crew = InstagramPostCrew()
                # Usar um dicionário diretamente
                inputs_dict = {
                    "genero": inputs.get('genero', 'Neutro'),
                    "caption": caption,
                    "describe": describe,
                    "estilo": inputs.get('estilo', 'Divertido, Alegre, Sarcástico e descontraído'),
                    "pessoa": inputs.get('pessoa', 'Terceira pessoa do singular'),
                    "sentimento": inputs.get('sentimento', 'Positivo'),
                    "tamanho": inputs.get('tamanho', '200 palavras'),
                    "emojs": inputs.get('emojs', 'sim'),
                    "girias": inputs.get('girias', 'sim')
                }
                final_caption = crew.kickoff(inputs=inputs_dict)  # Passar o dicionário
            except Exception as e:
                print(f"Erro ao gerar legenda: {str(e)}")
                final_caption = caption  # Usar a legenda original em caso de erro
            
            # Adicionar texto padrão ao final da legenda
            final_caption = final_caption + "\n\n-------------------"
            final_caption = final_caption + "\n\n Essa postagem foi toda realizada por um agente inteligente"
            final_caption = final_caption + "\n O agente desempenhou as seguintes ações:"
            final_caption = final_caption + "\n 1 - Idenficação e reconhecimento do ambiente do vídeo"
            final_caption = final_caption + "\n 2 - Aplicação de Filtros de contraste e autocorreção do vídeo"
            final_caption = final_caption + "\n 3 - Definição de uma persona específica com base nas preferências"
            final_caption = final_caption + "\n 4 - Criação da legenda com base no vídeo e na persona"
            final_caption = final_caption + "\n 5 - Postagem no feed do instagram"
            final_caption = final_caption + "\n\n-------------------"
            
            # Post to Instagram with enhanced rate limit handling
            print("Iniciando processo de publicação no Instagram...")
            
            # ... código para postar no Instagram ...
            
        except Exception as e:
            print(f"Erro ao processar o vídeo: {str(e)}")
            raise

    @staticmethod
    def send_instagram_carousel(image_paths, caption, inputs=None):
        """
        Send a carousel to Instagram with a caption.

        Args:
            image_paths (list): List of paths to the image files
            caption (str): Caption text
            inputs (dict): Optional configuration for post generation
        """
        result = None
        original_image_paths = image_paths
        uploaded_images = []
        uploader = ImageUploader()  # Reuse the same uploader instance
        
        # Validar caption antes do processamento
        if not caption or caption.lower() == "none":
            caption = "A Acesso IA está transformando processos com IA! 🚀"
            print(f"Caption vazia ou 'None'. Usando caption padrão: '{caption}'")
        
        try:
            if inputs is None:
                inputs = {
                    "estilo": "Divertido, Alegre, Sarcástico e descontraído",
                    "pessoa": "Terceira pessoa do singular",
                    "sentimento": "Positivo",
                    "tamanho": "200 palavras",
                    "genero": "Neutro",
                    "emojs": "sim",
                    "girias": "sim"
                }
            
            # Verificar se os arquivos existem
            for image_path in image_paths:
                if not os.path.exists(image_path):
                    raise FileNotFoundError(f"Arquivo de imagem não encontrado: {image_path}")
                
            border_image = os.path.join(Paths.SRC_DIR, "instagram", "moldura.png")
            
            # Process images with filter
            print("Aplicando filtros às imagens...")
            processed_image_paths = [FilterImage.process(image_path) for image_path in image_paths]
            
            # First upload to get image descriptions
            print("Obtendo descrições das imagens...")
            descriptions = []
            for image_path in processed_image_paths:
                try:
                    temp_image = uploader.upload_from_path(image_path)
                    uploaded_images.append(temp_image)
                    describe = ImageDescriber.describe(temp_image['url'])
                    descriptions.append(describe)
                    
                    # Try to delete the temporary image immediately after getting description
                    if temp_image.get("deletehash"):
                        print(f"Deletando imagem temporária usada para descrição...")
                        if uploader.delete_image(temp_image["deletehash"]):
                            uploaded_images.remove(temp_image)
                except Exception as e:
                    print(f"Erro ao obter descrição da imagem: {str(e)}")
                    descriptions.append("Imagem para publicação no Instagram.")
                    
            # Add border and prepare final images
            print("Aplicando bordas e filtros...")
            bordered_image_paths = []
            for image_path in processed_image_paths:
                try:
                    image = ImageWithBorder.create_bordered_image(
                        border_path=border_image,
                        image_path=image_path,
                        output_path=image_path                
                    )
                    bordered_image_paths.append(image_path)
                except Exception as e:
                    print(f"Erro ao aplicar borda à imagem: {str(e)}")
                    bordered_image_paths.append(image_path)  # Usar a imagem original em caso de erro
            
            # Upload final images
            print("Enviando imagens para publicação...")
            final_images = []
            for image_path in bordered_image_paths:
                try:
                    final_image = uploader.upload_from_path(image_path)
                    final_images.append(final_image)
                    uploaded_images.append(final_image)
                except Exception as e:
                    print(f"Erro ao fazer upload da imagem final: {str(e)}")
                    raise
            
            # Generate caption
            print("Gerando legenda...")
            try:
                crew = InstagramPostCrew()
                # Usar um dicionário diretamente
                inputs_dict = {
                    "genero": inputs.get('genero', 'Neutro'),
                    "caption": caption,
                    "describe": "\n".join(descriptions),
                    "estilo": inputs.get('estilo', 'Divertido, Alegre, Sarcástico e descontraído'),
                    "pessoa": inputs.get('pessoa', 'Terceira pessoa do singular'),
                    "sentimento": inputs.get('sentimento', 'Positivo'),
                    "tamanho": inputs.get('tamanho', '200 palavras'),
                    "emojs": inputs.get('emojs', 'sim'),
                    "girias": inputs.get('girias', 'sim')
                }
                final_caption = crew.kickoff(inputs=inputs_dict)  # Passar o dicionário
            except Exception as e:
                print(f"Erro ao gerar legenda: {str(e)}")
                final_caption = caption  # Usar a legenda original em caso de erro
            
            # Adicionar texto padrão ao final da legenda
            final_caption = final_caption + "\n\n-------------------"
            final_caption = final_caption + "\n\n Essa postagem foi toda realizada por um agente inteligente"
            final_caption = final_caption + "\n O agente desempenhou as seguintes ações:"
            final_caption = final_caption + "\n 1 - Idenficação e reconhecimento do ambiente das imagens"
            final_caption = final_caption + "\n 2 - Aplicação de Filtros de contraste e autocorreção das imagens"
            final_caption = final_caption + "\n 3 - Aplicação de moldura específica"
            final_caption = final_caption + "\n 4 - Definição de uma persona específica com base nas preferências"
            final_caption = final_caption + "\n 5 - Criação da legenda com base nas imagens e na persona"
            final_caption = final_caption + "\n 6 - Postagem no feed do instagram"
            final_caption = final_caption + "\n\n-------------------"
            
            # Post to Instagram with enhanced rate limit handling
            print("Iniciando processo de publicação no Instagram...")
            
            # ... código para postar no Instagram ...
            
        except Exception as e:
            print(f"Erro ao processar as imagens: {str(e)}")
            raise

    @staticmethod
    def send_reels(video_path, caption, inputs=None):
        """
        Send a video to Instagram as a Reel
        
        Args:
            video_path (str): Path to the video file
            caption (str): Caption text
            inputs (dict): Optional configuration for post generation
            
        Returns:
            dict: Result information including post ID and URL
        """
        # Import here to avoid circular imports
        from src.instagram.instagram_reels_publisher import ReelsPublisher

        try:
            # Initialize publisher
            publisher = ReelsPublisher()
            
            # Process hashtags if provided in inputs
            hashtags = None
            if inputs and 'hashtags' in inputs:
                hashtags = inputs['hashtags']

            # Set share to feed option
            share_to_feed = True
            if inputs and 'share_to_feed' in inputs:
                share_to_feed = inputs['share_to_feed']

            # Upload and publish the reel
            result = publisher.upload_local_video_to_reels(
                video_path=video_path,
                caption=caption,
                hashtags=hashtags,
                optimize=True,  # Always optimize video for best results
                share_to_feed=share_to_feed
            )

            if not result:
                print(f"Failed to publish reel from {video_path}")
                return None

            print(f"Reel published successfully. ID: {result.get('id')}")
            return result

        except Exception as e:
            print(f"Error publishing reel: {e}")
            import traceback
            print(traceback.format_exc())
            return None
    @staticmethod
    def send_carousel(media_paths, caption, inputs):
        """
        Envia um carrossel de imagens para o Instagram
        
        Args:
            media_paths (list): Lista de caminhos dos arquivos de mídia (imagens)
            caption (str): Legenda do post
            inputs (dict): Configurações adicionais
            
        Returns:
            dict: Resultado do envio
        """
        try:
            logger.info(f"[CAROUSEL] Iniciando processamento do carrossel com {len(media_paths)} imagens")
            
            # Verificar se há pelo menos 2 imagens válidas
            if len(media_paths) < 2:
                raise Exception(f"Número insuficiente de imagens para criar um carrossel. Encontradas: {len(media_paths)}")
            
            # Verificar se os arquivos existem antes de prosseguir
            valid_paths = []
            for path in media_paths:
                if os.path.exists(path):  # Fixed extra parenthesis here
                    valid_paths.append(path)
                else:
                    logger.error(f"[CAROUSEL] ERRO: Arquivo não encontrado: {path}")
            
            if len(valid_paths) < 2:
                raise Exception(f"Número insuficiente de imagens válidas para criar um carrossel. Válidas: {len(valid_paths)}")
            
            logger.info(f"[CAROUSEL] {len(valid_paths)} imagens válidas encontradas, iniciando verificação de proporções")
            
            # Normalize images to have the same aspect ratio (new step)
            try:
                logger.info("[CAROUSEL] Normalizando imagens para mesma proporção...")
                normalized_paths = CarouselNormalizer.normalize_carousel_images(valid_paths)
                
                if len(normalized_paths) < 2:
                    logger.error("[CAROUSEL] Falha ao normalizar imagens do carrossel")
                    raise Exception("Falha ao normalizar imagens do carrossel")
                    
                logger.info(f"[CAROUSEL] {len(normalized_paths)} imagens normalizadas com sucesso")
                
                # Replace valid_paths with normalized_paths
                valid_paths = normalized_paths
            except Exception as e:
                logger.warning(f"[CAROUSEL] Erro ao normalizar imagens: {str(e)}. Tentando prosseguir com as originais.")
                # Continue with original images if normalization fails
            
            # Instanciar o serviço de carrossel do Instagram
            from src.instagram.instagram_carousel_service import InstagramCarouselService
            from src.instagram.carousel_poster import upload_carousel_images
            
            # Clear any existing carousel cache first
            try:
                # Try to call the clear API endpoint
                requests.post("http://localhost:5001/debug/carousel/clear", timeout=2)
            except:
                pass  # Ignore if the endpoint isn't available
            
            # Certificar-se de que temos as dependências necessárias
            service = InstagramCarouselService()
            
            # Verificar explicitamente as permissões do token
            is_valid, missing_permissions = service.check_token_permissions()
            if not is_valid:
                logger.error(f"[CAROUSEL] Token de API do Instagram não tem todas as permissões necessárias: {missing_permissions}")
                raise Exception(f"O token do Instagram não possui as permissões necessárias: {', '.join(missing_permissions)}")
            
            # Verificar credenciais
            if not service.instagram_account_id or not service.access_token:
                raise Exception("Credenciais do Instagram não configuradas corretamente")
            
            logger.info(f"[CAROUSEL] Credenciais verificadas, iniciando upload das imagens")
            
            # Fazer upload das imagens e obter URLs
            def progress_update(current, total):
                logger.info(f"[CAROUSEL] Upload de imagens: {current}/{total}")
                
            success, uploaded_images, image_urls = upload_carousel_images(valid_paths, progress_callback=progress_update)
            
            logger.info(f"[CAROUSEL] Resultado do upload: success={success}, {len(image_urls)} URLs obtidas")
            
            if not success:
                raise Exception("Falha no upload de uma ou mais imagens do carrossel")
            
            if len(image_urls) < 2:
                raise Exception(f"Número insuficiente de URLs para criar um carrossel: {len(image_urls)}")
            
            logger.info(f"[CAROUSEL] URLs das imagens: {image_urls}")
            
            # Postar o carrossel no Instagram, com retentativas 
            max_attempts = 3
            retry_delay = 15  # seconds
            
            for attempt in range(max_attempts):
                logger.info(f"[CAROUSEL] Tentativa {attempt+1}/{max_attempts} de publicação do carrossel no Instagram")
                
                try:
                    post_id = service.post_carousel(image_urls, caption)
                    
                    if post_id:
                        logger.info(f"[CAROUSEL] Carrossel publicado com sucesso! ID: {post_id}")
                        return {"status": "success", "post_id": post_id}
                    else:
                        logger.error(f"[CAROUSEL] post_carousel retornou None na tentativa {attempt+1}")
                        
                        if attempt < max_attempts - 1:
                            logger.info(f"[CAROUSEL] Aguardando {retry_delay}s antes da próxima tentativa...")
                            time.sleep(retry_delay)
                            retry_delay *= 2  # Double delay for next attempt
                        else:
                            raise Exception("Falha ao publicar o carrossel após múltiplas tentativas")
                except Exception as e:
                    logger.error(f"[CAROUSEL] Erro na tentativa {attempt+1}: {str(e)}")
                    
                    if attempt < max_attempts - 1:
                        logger.info(f"[CAROUSEL] Aguardando {retry_delay}s antes da próxima tentativa...")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Double delay for next attempt
                    else:
                        raise
            
            # If we reach here, all attempts failed
            raise Exception("Falha ao publicar o carrossel no Instagram após todas as tentativas")
            
        except Exception as e:
            logger.error(f"[CAROUSEL] ERRO: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            
            # Clean up any temporary normalized images
            try:
                for path in valid_paths:
                    if "NamedTemporaryFile" in path and os.path.exists(path):
                        os.unlink(path)
                        logger.info(f"[CAROUSEL] Arquivo temporário removido: {path}")
            except Exception as cleanup_error:
                logger.error(f"[CAROUSEL] Erro ao limpar arquivos temporários: {str(cleanup_error)}")
                
            raise Exception(f"Erro ao enviar carrossel: {e}")
