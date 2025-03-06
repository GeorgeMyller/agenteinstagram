from src.instagram.describe_image_tool import ImageDescriber

# Insira aqui uma URL válida de uma imagem
image_url = "https://super.abril.com.br/wp-content/uploads/2017/03/cores-que-um-lagarto-pode-assumir-variam-conforme-seu-habitat.jpg?quality=70&strip=info&w=1024&h=682&crop=1"

resultado = ImageDescriber.describe(image_url)
print("Descrição da imagem:", resultado)
