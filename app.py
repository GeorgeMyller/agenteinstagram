# app.py

from src.services.message import Message
from src.utils.image_decode_save import ImageDecodeSaver
from src.services.instagram_send import InstagramSend
from flask import Flask, request, jsonify
import subprocess
import os

app = Flask(__name__)

border_image = "moldura.png"

@app.route("/messages-upsert", methods=['POST'])
def webhook():
    try:
        data = request.get_json()  
        
        print(data)
                
        msg = Message(data)
        texto = msg.get_text()
        
        if msg.scope == Message.SCOPE_GROUP:    
            print(f"Grupo: {msg.group_id}")
            
            if str(msg.group_id) == "120363383673368986":
                 
                if msg.message_type == msg.TYPE_IMAGE:
                    image_path = ImageDecodeSaver.process(msg.image_base64)
                    
                    try:
                        result = InstagramSend.send_instagram(image_path, texto)
                        if result:
                            print("Post processado e enviado ao Instagram.")
                        else:
                            print("Não foi possível confirmar o status do post.")
                    except Exception as e:
                        print(f"Erro durante o envio para o Instagram: {str(e)}")
                    finally:
                        # Cleanup temp file
                        if os.path.exists(image_path):
                            try:
                                os.remove(image_path)
                                print(f"A imagem {image_path} foi apagada com sucesso.")
                            except Exception as e:
                                print(f"Erro ao apagar arquivo temporário: {str(e)}")
                
    except Exception as e:
        print(f"Erro no processamento do webhook: {str(e)}")
        
    return jsonify({"status": "processed"}), 200

def disable_firewall():
    # Check the current firewall state
    state_command = ["/usr/libexec/ApplicationFirewall/socketfilterfw", "--getglobalstate"]
    try:
        result = subprocess.run(state_command, check=True, capture_output=True, text=True)
        # Expecting output like "State = 1" when enabled or "State = 0" when disabled.
        if "0" in result.stdout:
            print("Firewall já está desabilitado.")
            return
    except subprocess.CalledProcessError as e:
        print(f"Falha ao verificar o estado do firewall: {e.stderr}")
    
    # Attempt to disable the firewall if it is enabled
    command = ["sudo", "/usr/libexec/ApplicationFirewall/socketfilterfw", "--setglobalstate", "off"]
    try:
        print("Tentando desabilitar o firewall do macOS para a porta do app...")
        subprocess.run(command, check=True, capture_output=True, text=True)
        print("Firewall desabilitado com sucesso.")
    except subprocess.CalledProcessError as e:
        print(f"Falha ao desabilitar o firewall: {e.stderr}")

if __name__ == "__main__":
    disable_firewall()
    app.run(host="0.0.0.0", port=5001, debug=True)