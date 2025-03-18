from .message import Message

class MessageFactory:
    @staticmethod
    def create_message(data):
        """
        Cria uma instância de Message a partir dos dados recebidos
        Args:
            data: Dados brutos da mensagem
        Returns:
            Message: Uma instância de Message
        """
        return Message(data)