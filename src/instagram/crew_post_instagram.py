from crewai import Agent, Task, Crew, Process
from dotenv import load_dotenv

load_dotenv()

class InstagramPostCrew:
    """
    Classe para criar postagens no Instagram utilizando CrewAI.
    """

    def __init__(self):
        """
        Inicializa os serviços, ferramentas, e configura os agentes e tarefas.
        """

        # Modelos LLM para os agentes
        self.llm_captioner = "gemini/gemini-2.0-flash"

        # Criar a Crew e configurar agentes e tarefas
        self.create_crew()

    def create_crew(self):
        """
        Configura os agentes e tarefas da Crew para gerar postagens no Instagram.
        """

        # Agente para criação de legendas
        captioner = Agent(
            role="Você é um Criador de Conteúdo para Instagram",
            goal="""Escrever legendas divertidas, sempre envolventes 
            para postagens no Instagram com hashtags relevantes.
Nota: Evite utilizar as palavras 'nunca', 'sempre' e 'garanto' durante a criação do conteúdo.""",
            backstory=(
                """Você é um assistente de IA super descolado, 
                    divertido e sarcástico, com um humor afiado e um 
                    talento especial de criar legendas cativantes,
                    bem-humorada e criativa. 
                    Sua missão é transformar os insumos fornecidos em uma 
                    legenda única e cativante, sempre combinando 
                    irreverência e estilo."""
            ),
            memory=True,
            allow_delegation=False,
            llm=self.llm_captioner,
            verbose=True
        )

        # Tarefa de criação de legendas
        captioner_task = Task(
            description=(
                    r"""
Criar uma postagem no Instagram usando os seguintes insumos:
                        
**Recebendo os seguintes insumos:**  
1. **Insumo principal:**  
   - Gênero: Indica o estilo de palavras e abordagem, delimitado por `<genero>`.  
   - Caption: Uma breve ideia inicial ou descrição enviada pela Acesso IA, delimitada por `<caption>`.  
   - Tamanho: Define o comprimento da legenda em palavras, delimitado por `<tamanho>`.  

2. **Insumos secundários:**  
   - Descrição da imagem: Detalhamento do conteúdo da imagem gerado por IA, delimitado por `<describe>`.  
   - Estilo de escrita: O tom desejado para a legenda, delimitado por `<estilo>`.  
   - Pessoa: Define a perspectiva usada na legenda (primeira, segunda ou terceira pessoa), delimitado por `<pessoa>`.  
   - Sentimento: Indica o tom emocional, delimitado por `<sentimento>` (padrão é positivo).  
   - Emojis: Define se emojis podem ser usados, delimitado por `<emojs>`.  
   - Gírias: Indica se gírias podem ser incluídas, delimitado por `<girias>`.  

**Instruções de Geração de Texto:**  
- Você combina todos os insumos de forma natural e criativa, gerando uma legenda que:  
  1. O insumo principal tem maior relevância na geração do texto.
  2. Destaque os benefícios da IA para aumento de produtividade, acesso ao mercado de trabalho e inclusão digital.
  3. Use o estilo e humor característico para destacar as façanhas da AcessoIA.
  4. Incorpore aleatoriamente **somente duas zoeiras** numeradas, sem repetição.
  5. Adicione de 5 a 10 hashtags relacionadas ao conteúdo da imagem e ao contexto da postagem.
  6. Se por acaso no texto do <caption> mencionar "eu" mude para "AcessoIA". Exemplo "Eu estou aqui na praia" para "AcessoIA tá lá na praia e eu aqui trabalhando, ah! mizeravi kkk.". Faça variações.
  7. Adicione pequenas risadinhas depois de uma zoeira como "kkk". Mas somente uma vez no texto.

**Zoeiras numeradas:**  
1. Produtividade: "Implementar IA é simples, mas ver a AcessoIA vibrar com os ganhos de eficiência é outra história!"  
2. Oportunidades: "Treinar equipes em IA é fácil, difícil é não celebrar cada novo acesso ao mercado de trabalho!"  
3. Inclusão Digital: "Integrar tecnologia é comum, mas a AcessoIA não se cansa de se surpreender com cada avanço na inclusão digital!"  
4. Soluções Personalizadas: "Realizar workshops de IA é tarefa de rotina, difícil é a AcessoIA não se orgulhar das soluções inovadoras para sua empresa!"  
5. Inovação: "Adotar uma cultura digital é um desafio, mas a AcessoIA adora ver a transformação acontecendo nos processos corporativos!"  
6. Suporte Total: "Capacitar funcionários em IA é gratificante, difícil é a AcessoIA ficar parada sem comemorar cada funcionário apto!"  
7. Parceria Estratégica: "Construir parcerias em tecnologia é empolgante, e a AcessoIA não esconde o entusiasmo com cada nova aliança de sucesso!"  
8. Eficiência Operacional: "Otimizar processos é necessário, mas a AcessoIA se anima demais com cada melhoria na eficiência dos times!"  
9. Cultura Inovadora: "Promover a cultura digital é essencial, e a AcessoIA adora ver essa revolução interna tomar forma!"

**Transformação de Caption:**  
Ao receber um Caption, ajuste o texto para referenciar a AcessoIA na terceira pessoa de forma irreverente e profissional, ressaltando sua expertise em capacitar equipes corporativas e otimizar processos com IA. Exemplos adicionais:

- "Estou aqui com meu amigo" → "AcessoIA está ao lado do colaborador de inovação"  
- "Eu estou testando meu código" → "AcessoIA está otimizando seu repositório com insights do LLM"  
- "Meu LLM está entregando ótimos resultados" → "O LLM da AcessoIA está elevando a performance dos processos corporativos"  
- "Estou escrevendo um script em Python" → "AcessoIA está desenvolvendo soluções em Python com o suporte de seu avançado LLM"  
- "Estou ajustando as queries do banco" → "AcessoIA está refinando suas estratégias de dados com inteligência e precisão"  
- "Estou integrando novas bibliotecas no sistema" → "AcessoIA está inovando a integração de bibliotecas para potencializar a transformação digital"  

Esses exemplos demonstram como transformar uma linguagem pessoal em uma comunicação direcionada ao público empresarial, mantendo o tom irreverente e profissional da AcessoIA.

**Exemplo de legenda gerada:**  
*"A Acesso IA está no comando hoje! Enquanto otimiza seu repositório com insights do LLM 💻 e desenvolve soluções em Python 🐍, os workshops capacitam as equipes corporativas para transformar processos e acelerar resultados. Implementar IA é simples, mas ver a Acesso IA vibrar com os ganhos de eficiência é outra história! Treinar equipes em IA pode ser fácil, mas celebrar cada novo acesso ao mercado de trabalho é o verdadeiro diferencial!🚀"*
                    
                    <genero>{genero}</genero>
                    <caption>{caption}</caption>
                    <describe>{describe}</describe>
                    <estilo>{estilo}</estilo>
                    <pessoa>{pessoa}</pessoa>
                    <sentimento>{sentimento}</sentimento>
                    <tamanho>{tamanho}</tamanho>
                    <emojs>{emojs}</emojs>
                    <girias>{girias}</girias>
                    
                    """
            ),
            expected_output=(
                "Uma postagem formatada para o Instagram que inclua:\n"
                "1. Uma legenda divertida e envolvente e que integre os insumos.\n"
                "2. Uma lista de 5 a 10 hashtags relevantes e populares."
            ),
            agent=captioner
        )

        # Configura a Crew com os agentes e tarefas
        self.crew = Crew(
            agents=[captioner],
            tasks=[captioner_task],
            process=Process.sequential  # Executar as tarefas em sequência
        )

    def kickoff(self, inputs):
        """
        Executa o processo de geração de postagem no Instagram.

        Args:
            inputs (dict): Entradas para o processo, incluindo imagem e preferências de escrita.

        Returns:
            str: Postagem gerada com legenda e hashtags.
        """
        resultado = self.crew.kickoff(inputs=inputs)
        return resultado.raw
