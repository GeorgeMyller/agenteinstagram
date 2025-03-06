# app.py

from src.services.message import Message
from src.utils.image_decode_save import ImageDecodeSaver
from src.services.instagram_send import InstagramSend
from flask import Flask, request, jsonify
import subprocess

app = Flask(__name__)

border_image = "moldura.png"

@app.route("/messages-upsert", methods=['POST'])
def webhook():

    data = request.get_json()  
    
    print(data)
            
    msg = Message(data)
    texto = msg.get_text()
    

    if msg.scope == Message.SCOPE_GROUP:    
        
        print(f"Grupo: {msg.group_id}")
        
        if str(msg.group_id) == "120363383673368986":
             
            if msg.message_type == msg.TYPE_IMAGE:
                
                image_path = ImageDecodeSaver.process(msg.image_base64)
                
                InstagramSend.send_instagram(image_path, texto)
                
            
    return "" 

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
    app.run(host="0.0.0.0", port=5000, debug=True)