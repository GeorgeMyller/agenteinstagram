from PIL import Image


class ImageWithBorder:
    # Instagram API requirements
    MIN_IMG_SIZE = 320  # Minimum size in pixels (each dimension)
    MAX_IMG_SIZE = 1080  # Maximum recommended size in pixels (each dimension)
    MAX_ABSOLUTE_SIZE = 1440  # Maximum allowed size in pixels (each dimension)
    MIN_ASPECT_RATIO = 0.8  # 4:5 portrait orientation
    MAX_ASPECT_RATIO = 1.91  # Landscape orientation

    @staticmethod
    def create_bordered_image(image_path, border_path, output_path, preserve_original_size=True):
        """
        Cria a imagem com a borda e salva no caminho especificado.
        Agora preserva o tamanho original da imagem por padrão.

        Args:
            image_path (str): Caminho da imagem base.
            border_path (str): Caminho da borda.
            output_path (str): Caminho para salvar a imagem resultante.
            preserve_original_size (bool): Se True, preserva o tamanho original da imagem.
        Returns:
            str: Caminho da imagem resultante.
        """
        # Abrir a imagem e a borda
        image = Image.open(image_path)
        border = Image.open(border_path)
        
        # Log original image attributes
        print(f"Original Image - Size: {image.size}, Format: {image.format}, Mode: {image.mode}")
        
        # Convert image to RGB if it's RGBA
        if image.mode in ('RGBA', 'LA'):
            background = Image.new('RGB', image.size, (255, 255, 255))
            background.paste(image, mask=image.split()[-1])
            image = background
        
        # Redimensionar a borda para o tamanho da imagem original
        try:
            border_resized = border.resize(image.size, resample=Image.LANCZOS)
        except AttributeError:
            # Fallback para versões mais antigas do PIL
            border_resized = border.resize(image.size, Image.ANTIALIAS)
        
        print(f"Borda redimensionada - Tamanho: {border_resized.size}")
        
        # Criar uma nova imagem do tamanho da original
        result = Image.new("RGB", image.size, (255, 255, 255))
        result.paste(image, (0, 0))
        
        # Se a borda tem transparência, lidar corretamente com ela
        if border_resized.mode == 'RGBA':
            # Use o canal alpha da borda como máscara
            mask = border_resized.split()[3]
            result.paste(border_resized.convert('RGB'), (0, 0), mask=mask)
        else:
            result.paste(border_resized.convert('RGB'), (0, 0))
        
        # Check if the image needs resizing to meet Instagram requirements
        width, height = result.size
        aspect_ratio = width / height if height > 0 else 0
        needs_resize = False
        
        if width > ImageWithBorder.MAX_IMG_SIZE or height > ImageWithBorder.MAX_IMG_SIZE:
            needs_resize = True
            print(f"Image exceeds recommended size ({width}x{height}), will resize")
        
        if aspect_ratio < ImageWithBorder.MIN_ASPECT_RATIO or aspect_ratio > ImageWithBorder.MAX_ASPECT_RATIO:
            print(f"Warning: Aspect ratio ({aspect_ratio:.2f}) outside Instagram's recommended range ({ImageWithBorder.MIN_ASPECT_RATIO}-{ImageWithBorder.MAX_ASPECT_RATIO})")
        
        # Resize to meet Instagram's requirements if needed
        if needs_resize:
            if width > height:
                # Landscape orientation
                new_width = min(width, ImageWithBorder.MAX_IMG_SIZE)
                scale_factor = new_width / width
                new_height = int(height * scale_factor)
            else:
                # Portrait or square orientation
                new_height = min(height, ImageWithBorder.MAX_IMG_SIZE)
                scale_factor = new_height / height
                new_width = int(width * scale_factor)
            
            # Ensure dimensions are within Instagram's absolute limits
            if new_width > ImageWithBorder.MAX_ABSOLUTE_SIZE:
                new_width = ImageWithBorder.MAX_ABSOLUTE_SIZE
            if new_height > ImageWithBorder.MAX_ABSOLUTE_SIZE:
                new_height = ImageWithBorder.MAX_ABSOLUTE_SIZE
                
            # Resize the image
            try:
                result = result.resize((new_width, new_height), resample=Image.LANCZOS)
                print(f"Image resized to meet Instagram requirements: {new_width}x{new_height}")
            except AttributeError:
                # Fallback for older PIL versions
                result = result.resize((new_width, new_height), Image.ANTIALIAS)
                print(f"Image resized to meet Instagram requirements: {new_width}x{new_height}")
        
        # Log final image attributes
        print(f"Final Image - Size: {result.size}, Format: {result.format}, Mode: {result.mode}")
        
        # Salvar a imagem resultante
        result.save(output_path, format="JPEG", quality=100)
        return output_path


