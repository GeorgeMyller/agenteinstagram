from PIL import Image


class ImageWithBorder:
    @staticmethod
    def create_bordered_image(image_path, border_path, output_path, target_size=(1080, 1350)):
        """
        Cria a imagem com a borda e salva no caminho especificado.

        Args:
            image_path (str): Caminho da imagem base.
            border_path (str): Caminho da borda.
            output_path (str): Caminho para salvar a imagem resultante.
            target_size (tuple): Dimensão alvo para o corte central (largura, altura).
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
        
        # Calcular o corte central da imagem
        width, height = image.size
        left = (width - target_size[0]) // 2
        top = (height - target_size[1]) // 2
        right = left + target_size[0]
        bottom = top + target_size[1]
        cropped_image = image.crop((left, top, right, bottom))
        
        # Log cropped image attributes
        print(f"Cropped Image - Size: {cropped_image.size}, Format: {cropped_image.format}, Mode: {cropped_image.mode}")
        
        # Criar uma nova imagem RGB
        result = Image.new("RGB", border.size, (255, 255, 255))
        result.paste(cropped_image, (0, 0))
        
        # Se a borda tem transparência, precisamos lidar com ela corretamente
        if border.mode == 'RGBA':
            # Use o canal alpha da borda como máscara
            mask = border.split()[3]
            result.paste(border.convert('RGB'), (0, 0), mask=mask)
        else:
            result.paste(border.convert('RGB'), (0, 0))
        
        # Log final image attributes
        print(f"Final Image - Size: {result.size}, Format: {result.format}, Mode: {result.mode}")
        
        # Salvar a imagem resultante
        result.save(output_path, format="JPEG", quality=100)
        return output_path


