from PIL import Image
import os
import logging
import tempfile
import time

logger = logging.getLogger(__name__)

class InstagramImageValidator:
    """
    Validates images for Instagram posting requirements.
    Performs checks required by Instagram's API for various post types.
    """
    
    # Instagram API requirements
    MIN_IMG_SIZE = 320  # Minimum size in pixels (each dimension)
    MAX_IMG_SIZE = 1440  # Maximum size in pixels (each dimension)
    CAROUSEL_RATIO_TOLERANCE = 0.02  # 2% tolerance for aspect ratio consistency
    
    # Instagram supported aspect ratios
    MIN_ASPECT_RATIO = 0.8  # 4:5 portrait orientation
    MAX_ASPECT_RATIO = 1.91  # Landscape orientation
    
    @classmethod
    def validate_for_carousel(cls, image_paths, auto_normalize=False):
        """
        Validates that all images meet Instagram's carousel requirements.
        
        Args:
            image_paths (list): List of paths to images to be included in carousel
            auto_normalize (bool): If True, automatically normalize images
            
        Returns:
            tuple: If auto_normalize is False: (is_valid, message)
                  If auto_normalize is True: (is_valid, message, normalized_paths)
        """
        if not image_paths or len(image_paths) < 2:
            return (False, "Carrossel precisa de pelo menos 2 imagens") if not auto_normalize else (False, "Carrossel precisa de pelo menos 2 imagens", [])
        
        if len(image_paths) > 10:  # Instagram maximum
            return (False, "Máximo de 10 imagens permitidas no carrossel") if not auto_normalize else (False, "Máximo de 10 imagens permitidas no carrossel", [])
        
        # If auto_normalize is enabled, normalize images before validation
        if auto_normalize:
            normalized_paths = cls.normalize_for_carousel(image_paths)
            if normalized_paths:
                validation_result, message = cls.validate_for_carousel(normalized_paths, auto_normalize=False)
                return validation_result, message, normalized_paths
            return False, "Falha ao normalizar imagens", []
        
        # Track aspect ratios for consistency check
        aspect_ratios = []
        invalid_images = []
        processed_images = []  # Armazena caminhos de imagens processadas
        needs_processing = False
        
        for i, img_path in enumerate(image_paths):
            try:
                if not os.path.exists(img_path):
                    invalid_images.append(f"Imagem {i+1}: arquivo não encontrado")
                    processed_images.append(None)
                    continue
                    
                with Image.open(img_path) as img:
                    width, height = img.size
                    
                    # Check dimensions and flag for processing if needed
                    size_issue = False
                    if width < cls.MIN_IMG_SIZE or height < cls.MIN_IMG_SIZE:
                        invalid_images.append(f"Imagem {i+1}: tamanho muito pequeno ({width}x{height})")
                        size_issue = True
                    
                    if width > cls.MAX_IMG_SIZE or height > cls.MAX_IMG_SIZE:
                        invalid_images.append(f"Imagem {i+1}: tamanho muito grande ({width}x{height})")
                        size_issue = True
                        needs_processing = True
                    
                    if size_issue:
                        processed_images.append(None)
                        continue
                        
                    # Calculate aspect ratio
                    aspect_ratio = width / height
                    aspect_ratios.append(aspect_ratio)
                    processed_images.append(img_path)
                    
                    # Check format (Instagram accepts JPEG)
                    if img.format not in ['JPEG', 'JPG']:
                        logger.warning(f"Imagem {i+1} não está em formato JPEG/JPG. Formato atual: {img.format}")
                    
            except Exception as e:
                invalid_images.append(f"Imagem {i+1}: erro ao processar ({str(e)})")
                processed_images.append(None)
        
        # Se precisar de processamento automático e os erros são apenas de tamanho grande
        if needs_processing and all("tamanho muito grande" in issue for issue in invalid_images):
            logger.info("Tentando otimizar automaticamente imagens muito grandes para o carrossel")
            optimized_paths = []
            for i, img_path in enumerate(image_paths):
                if img_path and (i < len(processed_images) and processed_images[i] is None):
                    # Otimizar imagem grande
                    optimized_path = cls.resize_for_instagram(img_path)
                    optimized_paths.append(optimized_path)
                else:
                    optimized_paths.append(img_path)
            
            # Verificar novamente com imagens otimizadas
            return cls.validate_for_carousel(optimized_paths, auto_normalize)
        
        if invalid_images:
            return False, "Problemas encontrados:\n• " + "\n• ".join(invalid_images)
        
        # Check if all aspect ratios are similar (Instagram requires consistent ratios)
        if aspect_ratios:
            first_ratio = aspect_ratios[0]
            inconsistent_ratios = []
            for i, ratio in enumerate(aspect_ratios[1:], 2):
                # Allow tolerance
                if abs(first_ratio - ratio) / first_ratio > cls.CAROUSEL_RATIO_TOLERANCE:
                    inconsistent_ratios.append(f"As imagens devem ter proporções similares. Imagem 1 ({first_ratio:.2f}:1) difere da imagem {i} ({ratio:.2f}:1)")
            
            if inconsistent_ratios and auto_normalize:
                logger.info("Tentando normalizar proporções das imagens do carrossel")
                normalized_paths = cls.normalize_for_carousel(image_paths)
                if normalized_paths:
                    validation_result, message = cls.validate_for_carousel(normalized_paths, auto_normalize=False)
                    return validation_result, message, normalized_paths
            elif inconsistent_ratios:
                return False, inconsistent_ratios[0]
        
        return True, "Todas as imagens são válidas para o carrossel"

    @classmethod
    def normalize_for_carousel(cls, image_paths):
        """
        Normaliza imagens para o carrossel aplicando os mesmos padrões de imagens únicas.
        """
        if not image_paths:
            return []
            
        normalized_paths = []
        target_ratio = None
        
        # Primeira passagem: processar cada imagem individualmente
        for path in image_paths:
            try:
                # Usar o mesmo processamento de imagem única
                result = cls.process_single_photo(path)
                if result['status'] == 'success':
                    processed_path = result['image_path']
                    
                    # Calcular proporção da primeira imagem válida como referência
                    if target_ratio is None:
                        with Image.open(processed_path) as img:
                            width, height = img.size
                            target_ratio = width / height
                    
                    normalized_paths.append(processed_path)
                else:
                    logger.warning(f"Falha ao processar imagem {path}: {result['message']}")
            except Exception as e:
                logger.error(f"Erro ao processar imagem {path}: {str(e)}")
        
        # Segunda passagem: ajustar proporções para corresponder à primeira imagem
        if target_ratio and len(normalized_paths) > 1:
            final_paths = []
            for path in normalized_paths:
                try:
                    with Image.open(path) as img:
                        width, height = img.size
                        current_ratio = width / height
                        
                        # Se a proporção for muito diferente, ajustar
                        if abs(current_ratio - target_ratio) > cls.CAROUSEL_RATIO_TOLERANCE:
                            new_path = cls._adjust_aspect_ratio(img, path, target_ratio)
                            final_paths.append(new_path)
                        else:
                            final_paths.append(path)
                except Exception as e:
                    logger.error(f"Erro ao ajustar proporção da imagem {path}: {str(e)}")
                    final_paths.append(path)
            
            return final_paths
        
        return normalized_paths

    @classmethod
    def _adjust_aspect_ratio(cls, img, original_path, target_ratio):
        """
        Ajusta a proporção de uma imagem para corresponder à proporção alvo.
        """
        width, height = img.size
        current_ratio = width / height
        
        filename, ext = os.path.splitext(original_path)
        new_path = f"{filename}_adjusted{ext}"
        
        if current_ratio > target_ratio:
            # Imagem muito larga, cortar largura
            new_width = int(height * target_ratio)
            left = (width - new_width) // 2
            img_cropped = img.crop((left, 0, left + new_width, height))
        else:
            # Imagem muito alta, cortar altura
            new_height = int(width / target_ratio)
            top = (height - new_height) // 2
            img_cropped = img.crop((0, top, width, top + new_height))
        
        img_cropped.save(new_path, quality=95)
        return new_path

    @classmethod
    def resize_for_instagram(cls, image_path, output_path=None):
        """
        Resizes an image to fit Instagram requirements if needed.
        
        Args:
            image_path (str): Path to the image file
            output_path (str, optional): Output path for the resized image
            
        Returns:
            str: Path to the resized image
        """
        if output_path is None:
            filename, ext = os.path.splitext(image_path)
            output_path = f"{filename}_resized{ext}"
            
        try:
            with Image.open(image_path) as img:
                width, height = img.size
                
                # Check if resizing is needed
                if width > cls.MAX_IMG_SIZE or height > cls.MAX_IMG_SIZE:
                    # Calculate new dimensions while maintaining aspect ratio
                    if width > height:
                        new_width = cls.MAX_IMG_SIZE
                        new_height = int(height * (cls.MAX_IMG_SIZE / width))
                    else:
                        new_height = cls.MAX_IMG_SIZE
                        new_width = int(width * (cls.MAX_IMG_SIZE / height))
                    
                    # Resize image
                    img = img.resize((new_width, new_height), Image.LANCZOS)
                    img.save(output_path, quality=95)
                    logger.info(f"Imagem redimensionada: {width}x{height} -> {new_width}x{new_height}")
                    return output_path
                
                # If no resizing needed, return original path
                return image_path
                
        except Exception as e:
            logger.error(f"Erro ao redimensionar imagem: {str(e)}")
            return image_path

    @classmethod
    def process_single_photo(cls, image_path, output_dir=None):
        """
        Process a single photo for Instagram following the container workflow:
        1. Validates the image
        2. Optimizes/resizes if needed (corresponds to container processing)
        3. Prepares for publication
        4. Returns the ready-to-publish image path
        
        Args:
            image_path (str): Path to the original image
            output_dir (str, optional): Directory to save processed image
            
        Returns:
            dict: {
                'status': str ('success', 'error'),
                'image_path': str (path to processed image),
                'message': str (details about processing),
                'original_path': str (original image path)
            }
        """
        result = {
            'status': 'error',
            'original_path': image_path,
            'image_path': None,
            'message': ''
        }
        
        try:
            # 1. Check if file exists
            if not os.path.exists(image_path):
                result['message'] = "Arquivo não encontrado"
                logger.error(f"Image not found: {image_path}")
                return result
            
            # 2. Initial validation (simulates container creation)
            is_valid, issues = cls.validate_single_photo(image_path)
            if not is_valid:
                result['message'] = f"Validação falhou: {issues}"
                logger.warning(f"Image validation failed: {issues}")
                
                # Attempt to fix issues by optimizing (simulates container processing)
                logger.info(f"Attempting to optimize image: {image_path}")
                
            # 3. Processing phase (simulates IN_PROGRESS container status)
            logger.info(f"Processing image: {image_path}")
            processed_path = cls.optimize_for_instagram(image_path, output_dir)
            
            # 4. Final validation (simulates FINISHED container status)
            is_valid, issues = cls.validate_single_photo(processed_path)
            if not is_valid:
                result['message'] = f"Imagem processada ainda não atende requisitos: {issues}"
                return result
            
            # 5. Ready for publication (simulates media_publish step)
            result['status'] = 'success'
            result['image_path'] = processed_path
            result['message'] = "Imagem processada com sucesso e pronta para publicação"
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing image: {str(e)}")
            result['message'] = f"Erro ao processar imagem: {str(e)}"
            return result
    
    @classmethod
    def validate_single_photo(cls, image_path):
        """
        Validates a single photo against Instagram requirements.
        
        Args:
            image_path (str): Path to image file
            
        Returns:
            tuple: (is_valid, message)
        """
        issues = []
        
        try:
            if not os.path.exists(image_path):
                return False, "Arquivo não encontrado"
                
            with Image.open(image_path) as img:
                width, height = img.size
                
                # Check dimensions
                if width < cls.MIN_IMG_SIZE or height < cls.MIN_IMG_SIZE:
                    issues.append(f"Tamanho muito pequeno ({width}x{height})")
                
                if width > cls.MAX_IMG_SIZE or height > cls.MAX_IMG_SIZE:
                    issues.append(f"Tamanho muito grande ({width}x{height})")
                    
                # Check aspect ratio
                aspect_ratio = width / height
                if aspect_ratio < cls.MIN_ASPECT_RATIO:
                    issues.append(f"Proporção muito estreita ({aspect_ratio:.2f}:1)")
                elif aspect_ratio > cls.MAX_ASPECT_RATIO:
                    issues.append(f"Proporção muito larga ({aspect_ratio:.2f}:1)")
                
                # Check format
                if img.format not in ['JPEG', 'JPG', 'PNG']:
                    issues.append(f"Formato não suportado ({img.format})")
                
                # Check file size
                file_size_mb = os.path.getsize(image_path) / (1024 * 1024)
                if file_size_mb > 8:  # Instagram's 8MB limit
                    issues.append(f"Arquivo muito grande ({file_size_mb:.2f}MB)")
        
        except Exception as e:
            return False, f"Erro ao processar imagem: {str(e)}"
        
        if issues:
            return False, "; ".join(issues)
        return True, "Imagem válida para Instagram"
    
    @classmethod
    def optimize_for_instagram(cls, image_path, output_dir=None):
        """
        Optimize an image for Instagram by:
        1. Resizing to fit dimensions
        2. Correcting aspect ratio if needed
        3. Ensuring proper format
        
        Args:
            image_path (str): Path to original image
            output_dir (str, optional): Directory to save optimized image
            
        Returns:
            str: Path to optimized image
        """
        try:
            with Image.open(image_path) as img:
                # First resize if needed
                resized = cls.resize_for_instagram(image_path)
                
                # Generate output path
                if output_dir:
                    os.makedirs(output_dir, exist_ok=True)
                    base_name = os.path.basename(image_path)
                    optimized_path = os.path.join(output_dir, f"optimized_{int(time.time())}_{base_name}")
                else:
                    filename, ext = os.path.splitext(resized)
                    optimized_path = f"{filename}_optimized{ext}"
                
                # Check aspect ratio and crop if needed
                with Image.open(resized) as img:
                    width, height = img.size
                    aspect_ratio = width / height
                    
                    # Only fix aspect ratio if outside Instagram limits
                    if aspect_ratio < cls.MIN_ASPECT_RATIO:
                        # Too narrow, crop height
                        new_height = int(width / cls.MIN_ASPECT_RATIO)
                        top = (height - new_height) // 2
                        bottom = top + new_height
                        crop_box = (0, top, width, bottom)
                        img = img.crop(crop_box)
                        
                    elif aspect_ratio > cls.MAX_ASPECT_RATIO:
                        # Too wide, crop width
                        new_width = int(height * cls.MAX_ASPECT_RATIO)
                        left = (width - new_width) // 2
                        right = left + new_width
                        crop_box = (left, 0, right, height)
                        img = img.crop(crop_box)
                    
                    # Convert to RGB if needed
                    if img.mode not in ('RGB', 'L'):
                        img = img.convert('RGB')
                        
                    # Save as JPEG for best compatibility
                    img.save(optimized_path, format='JPEG', quality=95)
                    logger.info(f"Image optimized: {image_path} -> {optimized_path}")
                    
                    return optimized_path
                    
        except Exception as e:
            logger.error(f"Error optimizing image: {str(e)}")
            return image_path  # Return original if optimization fails
