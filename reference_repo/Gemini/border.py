from PIL import Image
import logging

logger = logging.getLogger(__name__)

class ImageWithBorder:
    @staticmethod
    def create_bordered_image(image_path, border_path, output_path, target_size=(1080, 1350)):
        """
        Cria a imagem com a borda e salva no caminho especificado.
        """
        try:
            image = Image.open(image_path)
            border = Image.open(border_path)
            logger.info(f"Original Image - Size: {image.size}, Format: {image.format}, Mode: {image.mode}")  # Consistent logging

            if image.mode in ('RGBA', 'LA'):
                background = Image.new('RGB', image.size, (255, 255, 255))
                background.paste(image, mask=image.split()[-1])
                image = background

            width, height = image.size
            left = (width - target_size[0]) // 2
            top = (height - target_size[1]) // 2
            right = left + target_size[0]
            bottom = top + target_size[1]

            cropped_image = image.crop((left, top, right, bottom))
            logger.info(f"Cropped Image - Size: {cropped_image.size}, Format: {cropped_image.format}, Mode: {cropped_image.mode}")  # Consistent logging
            result = Image.new("RGB", border.size, (255, 255, 255))
            result.paste(cropped_image, (0, 0))

            if border.mode == 'RGBA':
                mask = border.split()[3]
                result.paste(border.convert('RGB'), (0, 0), mask=mask)
            else:
                result.paste(border.convert('RGB'), (0, 0))

            logger.info(f"Final Image - Size: {result.size}, Format: {result.format}, Mode: {result.mode}") # Consistent logging
            result.save(output_path, format="JPEG", quality=100)
            return output_path
        except Exception as e:
            logger.exception(f"Erro ao criar imagem com borda: {e}") # Consistent logging
            raise