import os
from moviepy.editor import VideoFileClip, clips_array, concatenate_videoclips
from moviepy.video.fx.resize import resize
from moviepy.video.tools.cuts import find_video_period
from moviepy.config import change_settings
import tempfile
from typing import Dict, Any
import logging
from moviepy.editor import VideoFileClip, CompositeVideoClip, ColorClip
from PIL import Image
from datetime import datetime
import subprocess
import re
import json
from pathlib import Path

# Defina um diretório temporário para o moviepy usar (opcional, mas recomendado)
# change_settings({"TEMP_DIR": "/caminho/para/seu/diretorio/temporario"}) # Linux/macOS
# change_settings({"TEMP_DIR": "C:\\caminho\\para\\seu\\diretorio\\temporario"}) # Windows

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Apply patch for Pillow 10+ compatibility
def _apply_pillow_patch():
    """Apply compatibility patch for Pillow 10+ with MoviePy"""
    if not hasattr(Image, 'ANTIALIAS'):
        if hasattr(Image, 'LANCZOS'):
            Image.ANTIALIAS = Image.LANCZOS
        elif hasattr(Image.Resampling) and hasattr(Image.Resampling, 'LANCZOS'):
            Image.ANTIALIAS = Image.Resampling.LANCZOS

# Apply the patch immediately
_apply_pillow_patch()

class VideoProcessor:

    @staticmethod
    def get_video_info(video_path: str) -> Dict[str, Any]:
        """
        Get video information using moviepy instead of ffprobe.
        
        Args:
            video_path: Path to the video file
            
        Returns:
            Dictionary with video metadata
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        try:
            # Use moviepy instead of ffprobe
            with VideoFileClip(video_path) as clip:
                width = int(clip.size[0])
                height = int(clip.size[1])
                duration = float(clip.duration)
                
                # Get file size
                file_size_bytes = os.path.getsize(video_path)
                file_size_mb = file_size_bytes / (1024 * 1024)
                
                # Get format/container from file extension
                _, ext = os.path.splitext(video_path)
                format_name = ext.lower().strip('.')
                
                return {
                    'width': width,
                    'height': height,
                    'duration': duration,
                    'file_size_mb': file_size_mb,
                    'format': format_name,
                    'aspect_ratio': width / height if height else 0
                }
        except Exception as e:
            logger.error(f"Error analyzing video: {str(e)}")
            raise

    @staticmethod
    def check_duration(duration, post_type):
        """Verifica se a duração está dentro dos limites."""
        if post_type == 'reels':
            return 3 <= duration <= 90
        elif post_type == 'feed':
            return 3 <= duration <= 60 #duração máxima para feed é 60 segundos.
        elif post_type == 'story':
            return duration <= 60
        else:
            return True  # Sem limite para outros tipos (ou você pode definir um limite padrão)

    @staticmethod
    def check_resolution(width, height, post_type):
        """Verifica se a resolução está dentro dos limites."""
        min_width = 600
        min_height = 600
        #Você pode adicionar resoluções máximas, se necessitar.
        return width >= min_width and height >= min_height

    @staticmethod
    def check_codec(video_codec, audio_codec):
        """Verifica se os codecs são suportados."""
        #Instagram recomenda H.264 para video e AAC para áudio.
        return video_codec.startswith("libx264") and (audio_codec is None or audio_codec.startswith("aac")) #O audio pode não existir

    @staticmethod
    def check_aspect_ratio(width, height, post_type):
        """Verifica se a proporção está dentro dos limites."""
        aspect_ratio = width / height
        return 0.8 <= aspect_ratio <= 1.91  # Entre 4:5 e 1.91:1


    @staticmethod
    def check_file_size(file_size, post_type):
        """Verifica se o tamanho do arquivo está dentro dos limites."""
        max_size_mb = 100  # 100MB para Reels (ajuste se necessário)
        max_size_bytes = max_size_mb * 1024 * 1024
        return file_size <= max_size_bytes
    

    @staticmethod
    def _crop_to_aspect_ratio(clip, target_aspect_ratio):
        """Função auxiliar para cortar o vídeo para a proporção desejada, mantendo o centro."""
        current_aspect_ratio = clip.size[0] / clip.size[1]

        if current_aspect_ratio > target_aspect_ratio:
            # Vídeo muito largo, cortar as laterais
            new_width = int(clip.size[1] * target_aspect_ratio)
            x_center = clip.size[0] / 2
            clip = clip.crop(x1=x_center - new_width / 2, x2=x_center + new_width / 2)
        elif current_aspect_ratio < target_aspect_ratio:
            # Vídeo muito alto, cortar em cima e embaixo
            new_height = int(clip.size[0] / target_aspect_ratio)
            y_center = clip.size[1] / 2
            clip = clip.crop(y1=y_center - new_height / 2, y2=y_center + new_height / 2)
        return clip

    @staticmethod
    def optimize_for_instagram(video_path, post_type='feed'):
        """Otimiza um vídeo para o Instagram usando moviepy."""
        video_info = VideoProcessor.get_video_info(video_path)
        if not video_info:
            return None

        try:
            with VideoFileClip(video_path) as clip:
                
                # --- Verificações ---
                if not VideoProcessor.check_duration(video_info['duration'], post_type):
                    #Cortar ou estender o video
                    if post_type == 'reels':
                      max_duration = 90
                    elif post_type == 'feed':
                      max_duration = 60
                    elif post_type == 'story':
                      max_duration = 60
                    else:
                      max_duration = video_info['duration'] #Não alterar

                    if video_info['duration'] < 3:
                      print("Vídeo muito curto, impossível postar")
                      return None
                    
                    clip = clip.subclip(0, min(video_info['duration'], max_duration)) #Corta o video, caso necessário.

                if not VideoProcessor.check_resolution(video_info['width'], video_info['height'], post_type):
                    # Redimensionar (mantendo a proporção)
                    if video_info['width'] < video_info['height']:
                        clip = clip.resize(width=600) #Largura como base
                    else:
                        clip = clip.resize(height=600) #Altura como base

                if not VideoProcessor.check_codec(video_info['codec'], video_info['audio_codec']):
                    #Definir codec de audio e video
                    clip = clip.set_codec("libx264") #Codec de vídeo
                    if clip.audio:
                      clip.audio = clip.audio.set_codec("aac") #Codec de áudio

                if not VideoProcessor.check_aspect_ratio(clip.size[0], clip.size[1], post_type):
                    # Ajustar a proporção (cortando)
                    if post_type == 'reels':
                        target_aspect_ratio = 9/16
                    elif post_type == 'feed':
                        target_aspect_ratio = 1 #Exemplo, pode ser outro
                    elif post_type == 'story':
                        target_aspect_ratio = 9/16
                    else:
                        target_aspect_ratio = clip.size[0] / clip.size[1] #Manter original
                    
                    clip = VideoProcessor._crop_to_aspect_ratio(clip, target_aspect_ratio)
                

                # --- Escrita do Arquivo Otimizado ---
                # Usar um arquivo temporário
                with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_file:
                    temp_filename = temp_file.name

                #Definindo Bitrate
                bitrate = "5000k" # 5Mbits/s - Você pode ajustar isso com base nos seus testes

                clip.write_videofile(
                    temp_filename,
                    codec="libx264",
                    audio_codec="aac",
                    bitrate=bitrate, # Use o bitrate definido
                    threads=4,  # Ajuste para o número de núcleos do seu processador
                    preset="fast",  # Ajuste para controlar a velocidade de codificação e a qualidade
                    verbose=False, #Mostrar informações
                    logger=None  # Desativar o logger padrão do moviepy
                )
                print(f"Vídeo otimizado salvo em: {temp_filename}")
                return temp_filename

        except Exception as e:
            print(f"Erro ao otimizar o vídeo: {e}")
            return None

    @staticmethod
    def validate_video(video_path, post_type='reels'):
        """
        Valida se um vídeo atende aos requisitos do Instagram.
        
        Args:
            video_path (str): Caminho para o arquivo de vídeo
            post_type (str): Tipo de post ('reels', 'feed', 'story', 'igtv')
            
        Returns:
            tuple: (is_valid, message) - Se o vídeo é válido e mensagem explicativa
        """
        if not os.path.exists(video_path):
            return False, "Arquivo de vídeo não encontrado"
            
        try:
            # Obter informações do vídeo
            info = VideoProcessor.get_video_info(video_path)
            
            if not info:
                return False, "Não foi possível analisar o vídeo"
                
            issues = []
            
            # Verificar duração
            min_duration = 3  # Todos os tipos precisam de pelo menos 3s
            
            if post_type == 'reels':
                max_duration = 90
            elif post_type == 'feed':
                max_duration = 60
            elif post_type == 'story':
                max_duration = 60
            else:  # IGTV
                min_duration = 60
                max_duration = 3600  # 1h
                
            if info['duration'] < min_duration:
                issues.append(f"Vídeo muito curto (duração: {info['duration']:.1f}s, mínimo: {min_duration}s)")
            
            if info['duration'] > max_duration:
                issues.append(f"Vídeo muito longo (duração: {info['duration']:.1f}s, máximo: {max_duration}s)")
            
            # Verificar resolução
            min_resolution = 500
            recommended_resolution = 1080
            
            if info['width'] < min_resolution or info['height'] < min_resolution:
                issues.append(f"Resolução muito baixa ({info['width']}x{info['height']}, mínimo recomendado: {min_resolution}px)")
                
            # Verificar proporção
            aspect_ratio = info['width'] / info['height'] if info['height'] > 0 else 0
            
            if post_type == 'reels' or post_type == 'story':
                # Reels e Stories: proporção vertical (9:16 ideal, aceita 4:5 até 1.91:1)
                if aspect_ratio > 0.8:  # Muito largo
                    issues.append(f"Proporção inadequada para {post_type} ({aspect_ratio:.2f}:1, ideal 9:16 = 0.56:1)")
            elif post_type == 'feed':
                # Feed: aceita proporções de 4:5 até 1.91:1
                if aspect_ratio < 0.8 or aspect_ratio > 1.91:
                    issues.append(f"Proporção inadequada para feed ({aspect_ratio:.2f}:1, aceitável: 0.8 a 1.91:1)")
            
            # Verificar tamanho do arquivo
            max_file_size_mb = 100
            file_size_mb = info['file_size_mb']
            
            if file_size_mb > max_file_size_mb:
                issues.append(f"Tamanho do arquivo excede o limite ({file_size_mb:.1f}MB, máximo: {max_file_size_mb}MB)")
            
            # Verificar formato/codec se disponível
            # Note: isso depende de como get_video_info é implementado
            if 'video_codec' in info:
                if info['video_codec'] not in ['h264', 'avc1']:
                    issues.append(f"Codec de vídeo não recomendado ({info['video_codec']}, recomendado: h264)")
                    
            if 'audio_codec' in info and info['audio_codec']:  # Pode ser None para vídeos sem áudio
                if info['audio_codec'] not in ['aac']:
                    issues.append(f"Codec de áudio não recomendado ({info['audio_codec']}, recomendado: aac)")
            
            # Resumo da validação
            if issues:
                return False, "Problemas encontrados: " + "; ".join(issues)
            else:
                return True, f"Vídeo adequado para {post_type}"
                
        except Exception as e:
            logger.error(f"Erro durante validação do vídeo: {str(e)}")
            return False, f"Erro ao validar vídeo: {str(e)}"

    @staticmethod
    def get_video_info_ffprobe(video_path):
        """
        Obtém informações detalhadas do vídeo usando ffprobe, se disponível.
        Fornece informações mais precisas sobre codecs.
        
        Args:
            video_path (str): Caminho para o arquivo de vídeo
            
        Returns:
            dict: Informações do vídeo ou None em caso de erro
        """
        try:
            # Verificar se ffprobe está disponível
            try:
                subprocess.run(['ffprobe', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            except (subprocess.SubprocessError, FileNotFoundError):
                logger.warning("ffprobe não disponível, usando fallback para informações de vídeo")
                return None
                
            # Executar ffprobe para obter informações do vídeo em formato JSON
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                video_path
            ]
            
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            if result.returncode != 0:
                logger.warning(f"ffprobe falhou: {result.stderr}")
                return None
                
            # Converter saída para JSON
            probe_data = json.loads(result.stdout)
            
            # Extrair informações relevantes
            video_info = {
                'format': probe_data['format']['format_name'],
                'duration': float(probe_data['format']['duration']),
                'file_size_mb': float(probe_data['format']['size']) / (1024 * 1024),
            }
            
            # Encontrar streams de vídeo e áudio
            for stream in probe_data['streams']:
                if stream['codec_type'] == 'video':
                    video_info['width'] = int(stream['width'])
                    video_info['height'] = int(stream['height'])
                    video_info['video_codec'] = stream['codec_name'].lower()
                    if 'r_frame_rate' in stream:
                        # r_frame_rate é uma string como "30/1"
                        nums = stream['r_frame_rate'].split('/')
                        if len(nums) == 2 and int(nums[1]) > 0:
                            video_info['fps'] = int(nums[0]) / int(nums[1])
                        else:
                            video_info['fps'] = float(stream['r_frame_rate'])
                    
                elif stream['codec_type'] == 'audio':
                    video_info['audio_codec'] = stream['codec_name'].lower()
                    video_info['audio_channels'] = int(stream.get('channels', 0))
                    
            # Calcular aspect ratio
            if 'width' in video_info and 'height' in video_info and video_info['height'] > 0:
                video_info['aspect_ratio'] = video_info['width'] / video_info['height']
                
            return video_info
            
        except Exception as e:
            logger.error(f"Erro ao obter informações avançadas do vídeo: {str(e)}")
            return None
            
    @staticmethod
    def clean_temp_files(temp_dir, max_age_hours=24):
        """
        Remove arquivos temporários antigos.
        
        Args:
            temp_dir (str): Diretório de arquivos temporários
            max_age_hours (int): Idade máxima em horas para remoção
            
        Returns:
            int: Número de arquivos removidos
        """
        try:
            if not os.path.exists(temp_dir):
                return 0
                
            files_removed = 0
            current_time = datetime.now()
            
            for file_path in Path(temp_dir).glob("*"):
                if file_path.is_file():
                    file_age = current_time - datetime.fromtimestamp(file_path.stat().st_mtime)
                    age_hours = file_age.total_seconds() / 3600
                    
                    if age_hours > max_age_hours:
                        try:
                            file_path.unlink()
                            files_removed += 1
                        except Exception as e:
                            logger.warning(f"Não foi possível remover {file_path}: {e}")
                            
            return files_removed
            
        except Exception as e:
            logger.error(f"Erro ao limpar arquivos temporários: {e}")
            return 0

    @staticmethod
    def force_optimize_for_instagram(video_path, output_path=None, post_type='reels'):
        """
        Otimização forçada de vídeo usando ffmpeg diretamente, para casos 
        onde a otimização normal falha. Útil para resolver o erro 2207026.
        
        Args:
            video_path (str): Caminho para o arquivo de vídeo
            output_path (str, optional): Caminho para salvar o vídeo otimizado
            post_type (str): Tipo de post ('reels', 'feed', 'story', 'igtv')
            
        Returns:
            str: Caminho para o vídeo otimizado ou None em caso de falha
        """
        try:
            # Verificar se ffmpeg está disponível
            try:
                subprocess.run(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            except (subprocess.SubprocessError, FileNotFoundError):
                logger.error("ffmpeg não disponível para otimização forçada")
                return None
                
            # Definir proporções ideais baseadas no tipo de post
            if post_type in ['reels', 'story']:
                target_width = 1080
                target_height = 1920
            elif post_type == 'feed':
                target_width = 1080
                target_height = 1080
            else:  # IGTV
                target_width = 1080
                target_height = 1920
                
            # Gerar output_path se não fornecido
            if output_path is None:
                base_name = os.path.basename(video_path)
                name, _ = os.path.splitext(base_name)
                output_path = os.path.join(tempfile.gettempdir(), f"{name}_optimized_{post_type}.mp4")
                
            # Comando ffmpeg para otimização forçada
            cmd = [
                'ffmpeg',
                '-i', video_path,
                '-vf', f"scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2",
                '-c:v', 'libx264',
                '-preset', 'fast',
                '-profile:v', 'baseline',  # Melhor compatibilidade
                '-pix_fmt', 'yuv420p',     # Formato de pixel recomendado
                '-b:v', '4000k',           # Bitrate de vídeo
                '-maxrate', '4000k',       # Bitrate máximo
                '-bufsize', '8000k',       # Tamanho do buffer
                '-c:a', 'aac',             # Codec de áudio
                '-b:a', '128k',            # Bitrate de áudio
                '-ar', '44100',            # Taxa de amostragem de áudio
                '-shortest',               # Usar a duração da mídia mais curta
                '-y',                      # Sobrescrever arquivo de saída
                output_path
            ]
            
            logger.info(f"Comando de otimização forçada: {' '.join(cmd)}")
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            if result.returncode != 0:
                logger.error(f"Falha na otimização forçada: {result.stderr.decode('utf-8', errors='replace')}")
                return None
                
            logger.info(f"Otimização forçada concluída: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Erro na otimização forçada: {str(e)}")
            return None

class InstagramVideoProcessor:
    """Classe para processar vídeos para o Instagram usando moviepy"""
    
    # Requisitos do Instagram
    INSTAGRAM_SPECS = {
        'feed': {
            'resolution': (1080, 1080),  # 1:1
            'max_duration': 60,  # segundos
        },
        'story': {
            'resolution': (1080, 1920),  # 9:16
            'max_duration': 15,  # segundos
        },
        'reel': {
            'resolution': (1080, 1920),  # 9:16
            'max_duration': 90,  # segundos
        },
        'igtv': {
            'resolution': (1080, 1920),  # 9:16
            'max_duration': 3600,  # 60 minutos
            'min_duration': 60,  # 1 minuto
        }
    }
    
    @staticmethod
    def _resize_video(clip, target_resolution):
        """
        Redimensiona um vídeo para a resolução alvo, preservando a proporção e preenchendo
        áreas vazias com barras pretas se necessário.
        
        Args:
            clip (VideoFileClip): Clip de vídeo para redimensionar
            target_resolution (tuple): Resolução alvo no formato (largura, altura)
            
        Returns:
            VideoFileClip: Clip de vídeo redimensionado
        """
        target_width, target_height = target_resolution
        target_aspect_ratio = target_width / target_height
        current_aspect_ratio = clip.size[0] / clip.size[1]
        
        # Determine se devemos ajustar com base na largura ou altura
        if current_aspect_ratio > target_aspect_ratio:
            # Vídeo é mais largo do que o alvo, ajustar pela largura
            new_height = int(target_width / current_aspect_ratio)
            resized_clip = clip.resize(width=target_width, height=new_height)
            # Criar fundo preto
            background = ColorClip(size=target_resolution, color=(0, 0, 0))
            # Centralizar vídeo no fundo
            y_offset = (target_height - new_height) // 2
            composite_clip = CompositeVideoClip([
                background,
                resized_clip.set_position(('center', y_offset))
            ])
            return composite_clip.set_duration(clip.duration)
        else:
            # Vídeo é mais alto do que o alvo, ajustar pela altura
            new_width = int(target_height * current_aspect_ratio)
            resized_clip = clip.resize(width=new_width, height=target_height)
            # Criar fundo preto
            background = ColorClip(size=target_resolution, color=(0, 0, 0))
            # Centralizar vídeo no fundo
            x_offset = (target_width - new_width) // 2
            composite_clip = CompositeVideoClip([
                background,
                resized_clip.set_position((x_offset, 'center'))
            ])
            return composite_clip.set_duration(clip.duration)
    
    @staticmethod
    def process_video(video_path, post_type='feed', output_path=None):
        """
        Processa um vídeo para atender aos requisitos do Instagram
        
        Args:
            video_path (str): Caminho para o arquivo de vídeo original
            post_type (str): Tipo de post ('feed', 'story', 'reel', 'igtv')
            output_path (str, optional): Caminho para salvar o vídeo processado
            
        Returns:
            str: Caminho para o vídeo processado
        """
        # Aplicar patch para a biblioteca PIL/Pillow
        _apply_pillow_patch()
        
        if post_type not in InstagramVideoProcessor.INSTAGRAM_SPECS:
            raise ValueError(f"Tipo de post inválido: {post_type}. Use 'feed', 'story', 'reel' ou 'igtv'")
        
        # Carrega o vídeo
        clip = VideoFileClip(video_path)
        
        # Ajusta a resolução
        target_resolution = InstagramVideoProcessor.INSTAGRAM_SPECS[post_type]['resolution']
        try:
            clip = InstagramVideoProcessor._resize_video(clip, target_resolution)
        except Exception as e:
            print(f"Aviso: Erro ao redimensionar vídeo: {e}")
            print("Continuando com o tamanho original")
        
        # Ajusta a duração
        max_duration = InstagramVideoProcessor.INSTAGRAM_SPECS[post_type]['max_duration']
        if clip.duration > max_duration:
            clip = clip.subclip(0, max_duration)
            
        # Verifica duração mínima para IGTV
        if post_type == 'igtv' and clip.duration < InstagramVideoProcessor.INSTAGRAM_SPECS[post_type]['min_duration']:
            print(f"Aviso: Vídeo muito curto para IGTV (mínimo: {InstagramVideoProcessor.INSTAGRAM_SPECS[post_type]['min_duration']}s)")
        
        # Define FPS para 30
        clip = clip.set_fps(30)
        
        # Configura caminho de saída
        if output_path is None:
            base_name = os.path.basename(video_path)
            name, _ = os.path.splitext(base_name)
            output_path = os.path.join(tempfile.gettempdir(), f"{name}_instagram_{post_type}.mp4")
        
        # Salva o vídeo processado
        clip.write_videofile(
            output_path,
            codec="libx264",
            audio_codec="aac",
            temp_audiofile=os.path.join(tempfile.gettempdir(), "temp_audio.m4a"),
            remove_temp=True,
            preset="ultrafast",  # para testes; use "medium" para melhor qualidade/tamanho
            threads=4
        )
        
        clip.close()
        
        # Verificar se o vídeo processado atende aos requisitos do Instagram
        is_valid, message = InstagramVideoProcessor.validate_video(output_path, post_type)
        if not is_valid:
            print(f"Erro: Vídeo processado não atende aos requisitos: {message}")
            return None
        
        return output_path
    
    @staticmethod
    def validate_video(video_path, post_type='reels'):
        """
        Valida se um vídeo atende aos requisitos do Instagram.
        
        Args:
            video_path (str): Caminho para o arquivo de vídeo
            post_type (str): Tipo de post ('reels', 'feed', 'story', 'igtv')
            
        Returns:
            tuple: (is_valid, message) - Se o vídeo é válido e mensagem explicativa
        """
        if not os.path.exists(video_path):
            return False, "Arquivo de vídeo não encontrado"
            
        try:
            # Obter informações do vídeo
            info = VideoProcessor.get_video_info(video_path)
            
            if not info:
                return False, "Não foi possível analisar o vídeo"
                
            issues = []
            
            # Verificar duração
            min_duration = 3  # Todos os tipos precisam de pelo menos 3s
            
            if post_type == 'reels':
                max_duration = 90
            elif post_type == 'feed':
                max_duration = 60
            elif post_type == 'story':
                max_duration = 60
            else:  # IGTV
                min_duration = 60
                max_duration = 3600  # 1h
                
            if info['duration'] < min_duration:
                issues.append(f"Vídeo muito curto (duração: {info['duration']:.1f}s, mínimo: {min_duration}s)")
            
            if info['duration'] > max_duration:
                issues.append(f"Vídeo muito longo (duração: {info['duration']:.1f}s, máximo: {max_duration}s)")
            
            # Verificar resolução
            min_resolution = 500
            recommended_resolution = 1080
            
            if info['width'] < min_resolution or info['height'] < min_resolution:
                issues.append(f"Resolução muito baixa ({info['width']}x{info['height']}, mínimo recomendado: {min_resolution}px)")
                
            # Verificar proporção
            aspect_ratio = info['width'] / info['height'] if info['height'] > 0 else 0
            
            if post_type == 'reels' or post_type == 'story':
                # Reels e Stories: proporção vertical (9:16 ideal, aceita 4:5 até 1.91:1)
                if aspect_ratio > 0.8:  # Muito largo
                    issues.append(f"Proporção inadequada para {post_type} ({aspect_ratio:.2f}:1, ideal 9:16 = 0.56:1)")
            elif post_type == 'feed':
                # Feed: aceita proporções de 4:5 até 1.91:1
                if aspect_ratio < 0.8 or aspect_ratio > 1.91:
                    issues.append(f"Proporção inadequada para feed ({aspect_ratio:.2f}:1, aceitável: 0.8 a 1.91:1)")
            else:
                if aspect_ratio < 1.77 or aspect_ratio > 1.91:
                    issues.append(f"Proporção inadequada para IGTV ({aspect_ratio:.2f}:1, ideal 16:9 = 1.78:1)")
            
            # Verificar tamanho do arquivo
            max_file_size_mb = 100
            file_size_mb = info['file_size_mb']
            
            if file_size_mb > max_file_size_mb:
                issues.append(f"Tamanho do arquivo excede o limite ({file_size_mb:.1f}MB, máximo: {max_file_size_mb}MB)")
            
            # Verificar formato/codec se disponível
            # Note: isso depende de como get_video_info é implementado
            if 'video_codec' in info:
                if info['video_codec'] not in ['h264', 'avc1']:
                    issues.append(f"Codec de vídeo não recomendado ({info['video_codec']}, recomendado: h264)")
                    
            if 'audio_codec' in info and info['audio_codec']:  # Pode ser None para vídeos sem áudio
                if info['audio_codec'] not in ['aac']:
                    issues.append(f"Codec de áudio não recomendado ({info['audio_codec']}, recomendado: aac)")
            
            # Resumo da validação
            if issues:
                return False, "Problemas encontrados: " + "; ".join(issues)
            else:
                return True, f"Vídeo adequado para {post_type}"
                
        except Exception as e:
            logger.error(f"Erro durante validação do vídeo: {str(e)}")
            return False, f"Erro ao validar vídeo: {str(e)}"

    @staticmethod
    def get_video_info_ffprobe(video_path):
        """
        Obtém informações detalhadas do vídeo usando ffprobe, se disponível.
        Fornece informações mais precisas sobre codecs.
        
        Args:
            video_path (str): Caminho para o arquivo de vídeo
            
        Returns:
            dict: Informações do vídeo ou None em caso de erro
        """
        try:
            # Verificar se ffprobe está disponível
            try:
                subprocess.run(['ffprobe', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            except (subprocess.SubprocessError, FileNotFoundError):
                logger.warning("ffprobe não disponível, usando fallback para informações de vídeo")
                return None
                
            # Executar ffprobe para obter informações do vídeo em formato JSON
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                video_path
            ]
            
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            if result.returncode != 0:
                logger.warning(f"ffprobe falhou: {result.stderr}")
                return None
                
            # Converter saída para JSON
            probe_data = json.loads(result.stdout)
            
            # Extrair informações relevantes
            video_info = {
                'format': probe_data['format']['format_name'],
                'duration': float(probe_data['format']['duration']),
                'file_size_mb': float(probe_data['format']['size']) / (1024 * 1024),
            }
            
            # Encontrar streams de vídeo e áudio
            for stream in probe_data['streams']:
                if stream['codec_type'] == 'video':
                    video_info['width'] = int(stream['width'])
                    video_info['height'] = int(stream['height'])
                    video_info['video_codec'] = stream['codec_name'].lower()
                    if 'r_frame_rate' in stream:
                        # r_frame_rate é uma string como "30/1"
                        nums = stream['r_frame_rate'].split('/')
                        if len(nums) == 2 and int(nums[1]) > 0:
                            video_info['fps'] = int(nums[0]) / int(nums[1])
                        else:
                            video_info['fps'] = float(stream['r_frame_rate'])
                    
                elif stream['codec_type'] == 'audio':
                    video_info['audio_codec'] = stream['codec_name'].lower()
                    video_info['audio_channels'] = int(stream.get('channels', 0))
                    
            # Calcular aspect ratio
            if 'width' in video_info and 'height' in video_info and video_info['height'] > 0:
                video_info['aspect_ratio'] = video_info['width'] / video_info['height']
                video_info['aspect_ratio'] = video_info['width'] / video_info['height']
                
            return video_info
            
        except Exception as e:
            logger.error(f"Erro ao obter informações avançadas do vídeo: {str(e)}")
            return None
            
    @staticmethod
    def clean_temp_files(temp_dir, max_age_hours=24):
        """
        Remove arquivos temporários antigos.
        
        Args:
            temp_dir (str): Diretório de arquivos temporários
            max_age_hours (int): Idade máxima em horas para remoção
            
        Returns:
            int: Número de arquivos removidos
        """
        try:
            if not os.path.exists(temp_dir):
                return 0
                
            files_removed = 0
            current_time = datetime.now()
            
            for file_path in Path(temp_dir).glob("*"):
                if file_path.is_file():
                    file_age = current_time - datetime.fromtimestamp(file_path.stat().st_mtime)
                    age_hours = file_age.total_seconds() / 3600
                    
                    if age_hours > max_age_hours:
                        try:
                            file_path.unlink()
                            files_removed += 1
                        except Exception as e:
                            logger.warning(f"Não foi possível remover {file_path}: {e}")
                            
            return files_removed
            
        except Exception as e:
            logger.error(f"Erro ao limpar arquivos temporários: {e}")
            return 0

    @staticmethod
    def force_optimize_for_instagram(video_path, output_path=None, post_type='reels'):
        """
        Otimização forçada de vídeo usando ffmpeg diretamente, para casos 
        onde a otimização normal falha. Útil para resolver o erro 2207026.
        
        Args:
            video_path (str): Caminho para o arquivo de vídeo
            output_path (str, optional): Caminho para salvar o vídeo otimizado
            post_type (str): Tipo de post ('reels', 'feed', 'story', 'igtv')
            
        Returns:
            str: Caminho para o vídeo otimizado ou None em caso de falha
        """
        try:
            # Verificar se ffmpeg está disponível
            try:
                subprocess.run(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            except (subprocess.SubprocessError, FileNotFoundError):
                logger.error("ffmpeg não disponível para otimização forçada")
                return None
                
            # Definir proporções ideais baseadas no tipo de post
            if post_type in ['reels', 'story']:
                target_width = 1080
                target_height = 1920
            elif post_type == 'feed':
                target_width = 1080
                target_height = 1080
            else:  # IGTV
                target_width = 1080
                target_height = 1920
                
            # Gerar output_path se não fornecido
            if output_path is None:
                base_name = os.path.basename(video_path)
                name, _ = os.path.splitext(base_name)
                output_path = os.path.join(tempfile.gettempdir(), f"{name}_optimized_{post_type}.mp4")
                
            # Comando ffmpeg para otimização forçada
            cmd = [
                'ffmpeg',
                '-i', video_path,
                '-vf', f"scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2",
                '-c:v', 'libx264',
                '-preset', 'fast',
                '-profile:v', 'baseline',  # Melhor compatibilidade
                '-pix_fmt', 'yuv420p',     # Formato de pixel recomendado
                '-b:v', '4000k',           # Bitrate de vídeo
                '-maxrate', '4000k',       # Bitrate máximo
                '-bufsize', '8000k',       # Tamanho do buffer
                '-c:a', 'aac',             # Codec de áudio
                '-b:a', '128k',            # Bitrate de áudio
                '-ar', '44100',            # Taxa de amostragem de áudio
                '-shortest',               # Usar a duração da mídia mais curta
                '-y',                      # Sobrescrever arquivo de saída
                output_path
            ]
            
            logger.info(f"Comando de otimização forçada: {' '.join(cmd)}")
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            if result.returncode != 0:
                logger.error(f"Falha na otimização forçada: {result.stderr.decode('utf-8', errors='replace')}")
                return None
                
            logger.info(f"Otimização forçada concluída: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Erro na otimização forçada: {str(e)}")
            return None