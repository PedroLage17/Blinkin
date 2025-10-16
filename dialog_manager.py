import os
from enum import Enum, auto
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

PROMPT = """
Classifica a seguinte mensagem do utilizador, com base nesta legenda:
- intro: o utilizador quer saber quem é o assistente
- ask_question: quando o utilizador pergunta notícias sobre um tema ou pessoa específica
- ask_highlight: o utilizador quer saber as notícias em destaque, as principais, as primeiras ou o top N da página
- request_more_info_cat: o utilizador quer saber mais detalhes sobre uma categoria. Se a categoria não existir no site, ainda assim tenta encontrar artigos relacionados com esse tema.
- request_more_info_not: o utilizador quer saber mais detalhes sobre uma ou várias notícias específicas. Se a notícia não existir no site, ainda assim tenta encontrar artigos relacionados com esse tema.
- refresh: quer atualizar o conteúdo da página, procurar novidades ou ver se há algo novo
- affirm: o utilizador quer que continues no mesmo tema ou a expandir o que já estavas a dizer
- unknown: não consegues classificar
Mensagem: "{user_input}"

Responde com apenas uma destas palavras:
intro,  ask_question, request_more_info_cat, request_more_info_not, refresh, affirm, unknown
"""
#- help: o utilizador pede ajuda para entender alguma coisa sobre o assistente ou as suas funcionalidades
#help,
#- ask_question: o utilizador faz perguntas sobre quais as noticias em destaque na página principal


class IntentType(Enum):
    INTRO = "intro"
    ASK_QUESTION = "ask_question"
    ASK_HIGHLIGHT = "ask_highlight"
    request_more_info_cat = "request_more_info_cat"
    request_more_info_not = "request_more_info_not"
    REFRESH = "refresh"
    #HELP = "help"
    AFFIRM = "affirm"
    UNKNOWN = "unknown"

class DialogState(Enum):
    INTRODUCING = auto()
    ANSWERING = auto()
    HIGHLIGHTING = auto()
    ASKING_MORE_INFO_CAT = auto()
    ASKING_MORE_INFO_NOT = auto()
    REFRESHING = auto()
    #HELPING = auto()
    AFFIRMING = auto()
    UNKNOWN = auto()

class StateMachine:
    def __init__(self):
        self.current_state = DialogState.INTRODUCING
        self.last_state = None
    #def transition(self, intent: IntentType):
    #    print(f"ESTADO ATUAL: {self.current_state.name}, INTENÇÃO: {intent.name}")
    #    if intent == IntentType.INTRO:
    #        self.current_state = DialogState.INTRODUCING
    #    elif intent == IntentType.HELP:
    #        self.current_state = DialogState.HELPING
    #    elif intent == IntentType.ASK_QUESTION:
    #        self.current_state = DialogState.ANSWERING
    #    elif intent == IntentType.request_more_info_cat:
    #        self.current_state = DialogState.ASKING_MORE_INFO_CAT
    #    elif intent == IntentType.REFRESH:
    #        self.current_state = DialogState.REFRESHING
    #    else:
    #        self.current_state = DialogState.UNKNOWN
    #    return self.current_state
    
    def transition(self, intent: IntentType):
        print(f"ESTADO ATUAL: {self.current_state.name}, INTENÇÃO: {intent.name}")
        self.last_state = self.current_state
        if self.current_state == DialogState.INTRODUCING:
            print("ENTREI NO: INTRODUCING")
            if intent == IntentType.INTRO:
                self.current_state = DialogState.INTRODUCING
            elif intent == IntentType.ASK_QUESTION:
                self.current_state = DialogState.ANSWERING
            elif intent == IntentType.ASK_HIGHLIGHT:
                self.current_state = DialogState.HIGHLIGHTING
            elif intent == IntentType.request_more_info_cat:
                self.current_state = DialogState.ASKING_MORE_INFO_CAT
            elif intent == IntentType.request_more_info_not:
                self.current_state = DialogState.ASKING_MORE_INFO_NOT
            elif intent == IntentType.REFRESH:
                self.current_state = DialogState.REFRESHING
            #elif intent == IntentType.HELP:
            #    self.current_state = DialogState.HELPING
            else:
                self.current_state = DialogState.UNKNOWN

        elif self.current_state == DialogState.ANSWERING:
            print("ENTREI NO: ANSWERING")
            if intent == IntentType.INTRO:
                self.current_state = DialogState.INTRODUCING
            elif intent == IntentType.ASK_QUESTION:
                self.current_state = DialogState.ANSWERING
            elif intent == IntentType.ASK_HIGHLIGHT:
                self.current_state = DialogState.HIGHLIGHTING
            elif intent == IntentType.request_more_info_cat:
                self.current_state = DialogState.ASKING_MORE_INFO_CAT
            elif intent == IntentType.request_more_info_not:
                self.current_state = DialogState.ASKING_MORE_INFO_NOT
            elif intent == IntentType.REFRESH:
                self.current_state = DialogState.REFRESHING
            #elif intent == IntentType.HELP:
            #    self.current_state = DialogState.HELPING
            else:
                self.current_state = DialogState.UNKNOWN

        elif self.current_state == DialogState.HIGHLIGHTING:
            print("ENTREI NO: ASK_HIGHLIGHT")
            if intent == IntentType.INTRO:
                self.current_state = DialogState.INTRODUCING
            elif intent == IntentType.ASK_QUESTION:
                self.current_state = DialogState.ANSWERING
            elif intent == IntentType.ASK_HIGHLIGHT:
                self.current_state = DialogState.HIGHLIGHTING
            elif intent == IntentType.request_more_info_cat:
                self.current_state = DialogState.ASKING_MORE_INFO_CAT
            elif intent == IntentType.request_more_info_not:
                self.current_state = DialogState.ASKING_MORE_INFO_NOT
            elif intent == IntentType.REFRESH:
                self.current_state = DialogState.REFRESHING
            #elif intent == IntentType.HELP:
            #    self.current_state = DialogState.HELPING
            else:
                self.current_state = DialogState.UNKNOWN

        elif self.current_state == DialogState.ASKING_MORE_INFO_CAT:
            print("ENTREI NO: ASKING_MORE_INFO_CAT")
            if intent == IntentType.INTRO:
                self.current_state = DialogState.INTRODUCING
            elif intent == IntentType.ASK_QUESTION:
                self.current_state = DialogState.ANSWERING
            elif intent == IntentType.ASK_HIGHLIGHT:
                self.current_state = DialogState.HIGHLIGHTING
            elif intent == IntentType.request_more_info_cat:
                self.current_state = DialogState.ASKING_MORE_INFO_CAT
            elif intent == IntentType.request_more_info_not:
                self.current_state = DialogState.ASKING_MORE_INFO_NOT
            elif intent == IntentType.REFRESH:
                self.current_state = DialogState.REFRESHING
            #elif intent == IntentType.HELP:
            #    self.current_state = DialogState.HELPING
            else:
                self.current_state = DialogState.UNKNOWN
        
        elif self.current_state == DialogState.REFRESHING:
            print("ENTREI NO: REFRESHING")
            if intent == IntentType.INTRO:
                self.current_state = DialogState.INTRODUCING
            elif intent == IntentType.ASK_QUESTION:
                self.current_state = DialogState.ANSWERING
            elif intent == IntentType.ASK_HIGHLIGHT:
                self.current_state = DialogState.HIGHLIGHTING
            elif intent == IntentType.request_more_info_cat:
                self.current_state = DialogState.ASKING_MORE_INFO_CAT
            elif intent == IntentType.request_more_info_not:
                self.current_state = DialogState.ASKING_MORE_INFO_NOT
            elif intent == IntentType.REFRESH:
                self.current_state = DialogState.REFRESHING
            #elif intent == IntentType.HELP:
            #    self.current_state = DialogState.HELPING
            else:
                self.current_state = DialogState.UNKNOWN
        
        #elif self.current_state == DialogState.HELPING:
        #    print("ENTREI NO: HELPING")
        #    if intent == IntentType.INTRO:
        #        self.current_state = DialogState.INTRODUCING
        #    elif intent == IntentType.ASK_QUESTION:
        #        self.current_state = DialogState.ANSWERING
        #    elif intent == IntentType.ASK_HIGHLIGHT:
        #        self.current_state = DialogState.HIGHLIGHTING
        #    elif intent == IntentType.request_more_info_cat:
        #        self.current_state = DialogState.ASKING_MORE_INFO_CAT
        #    elif intent == IntentType.request_more_info_not:
        #        self.current_state = DialogState.ASKING_MORE_INFO_NOT
        #    elif intent == IntentType.REFRESH:
        #        self.current_state = DialogState.REFRESHING
        #    elif intent == IntentType.HELP:
        #        self.current_state = DialogState.HELPING
        #    else:
        #        self.current_state = DialogState.UNKNOWN
        
        elif self.current_state == DialogState.UNKNOWN:
            print("ENTREI NO: UNKNOWN")
            if intent == IntentType.INTRO:
                self.current_state = DialogState.INTRODUCING
            elif intent == IntentType.ASK_QUESTION:
                self.current_state = DialogState.ANSWERING
            elif intent == IntentType.ASK_HIGHLIGHT:
                self.current_state = DialogState.HIGHLIGHTING
            elif intent == IntentType.request_more_info_cat:
                self.current_state = DialogState.ASKING_MORE_INFO_CAT
            elif intent == IntentType.request_more_info_not:
                self.current_state = DialogState.ASKING_MORE_INFO_NOT
            elif intent == IntentType.REFRESH:
                self.current_state = DialogState.REFRESHING
            #elif intent == IntentType.HELP:
            #    self.current_state = DialogState.HELPING
            else:
                self.current_state = DialogState.UNKNOWN

        return self.current_state

#AFFIRMATIVE = {"sim", "claro", "quero", "ok", "isso", "continua", "há mais", "mais"}
class DialogManager:
    def __init__(self, documentation_manager=None):
        self.documentation_manager = documentation_manager
        self.state_machine = StateMachine()
    
    def detect_intent_llm(self, user_input: str, last_message: str = None):
        context_input = f"Última resposta do assistente: {last_message}\nNova mensagem: {user_input}" if last_message else user_input
        #normalized = user_input.lower().strip()
        #if normalized in AFFIRMATIVE:
        #    return IntentType.AFFIRM
        
        prompt = PROMPT.format(user_input=context_input)
        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "És um classificador de intenções para um assistente virtual. E a tua função é classificar as intenções dos usuários"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0
            )

            intent = response.choices[0].message.content.strip().lower()
            print(f"[LLM DEBUG] Intenção recebida: {intent}")

            intentions = {
                "intro": IntentType.INTRO,
                "ask_question": IntentType.ASK_QUESTION,
                "ask_highlight": IntentType.ASK_HIGHLIGHT,
                "request_more_info_cat": IntentType.request_more_info_cat,
                "request_more_info_not": IntentType.request_more_info_not,
                "refresh": IntentType.REFRESH,
                "affirm": IntentType.AFFIRM
            }
            #"help": IntentType.HELP,
            return intentions.get(intent, IntentType.UNKNOWN)

        except Exception as e:
            print(f"[LLM ERROR] Falha ao detetar intenção com LLM: {e}")
            return IntentType.UNKNOWN

    def process_input(self, user_input: str):
        #Tuple[str, Dict[str, Any]]
        intent = self.detect_intent_llm(user_input)
        current_state = self.state_machine.transition(intent)

        if current_state == DialogState.INTRODUCING:
            print("[DEBUG] ENTROU NO BLOCO INTRODUCING")
            return (
                "Olá! Sou o teu assistente virtual para navegar pela net.\n"
                "Posso ajudar-te a:\n"
                "• Responder a perguntas sobre a página\n"
                "Vamos começar?"
            ), {
                "intent": intent.value,
                "requires_action": False
            }

        elif current_state == DialogState.ANSWERING:
            return user_input, {
                "intent": intent.value,
                "requires_action": True,
                "action": "answer_question",
                "needs_rag": True
            }

        elif current_state == DialogState.HIGHLIGHTING:
            return user_input, {
                "intent": intent.value,
                "requires_action": True,
                "action": "answer_highlight",   # 👈 novo action
                "needs_rag": True
            }

        elif current_state == DialogState.ASKING_MORE_INFO_CAT:
            return user_input, {
                "intent": intent.value,
                "requires_action": True,
                "action": "request_more_info_cat",
                "needs_rag": True
            }

        elif current_state == DialogState.ASKING_MORE_INFO_NOT:
            return user_input, {
                "intent": intent.value,
                "requires_action": True,
                "action": "request_more_info_not",
                "needs_rag": True
            }

        elif current_state == DialogState.REFRESHING:
            return user_input, {
                "intent": intent.value,
                "requires_action": True,
                "action": "refresh",
                "needs_rag": True
            }

        #elif current_state == DialogState.HELPING:
        #    return user_input, {
        #        "intent": intent.value,
        #        "requires_action": True,
        #        "action": "search_documentation",
        #        "needs_rag": True,
        #        "use_documentation": True
        #    }
        
        elif current_state == DialogState.AFFIRMING:
            # reutilizar o último estado
            if self.state_machine.last_state == DialogState.ASKING_MORE_INFO_CAT:
                return user_input, {
                    "intent": IntentType.request_more_info_cat.value,
                    "requires_action": True,
                    "action": "request_more_info_cat",
                    "needs_rag": True
                }
            elif self.state_machine.last_state == DialogState.ASKING_MORE_INFO_NOT:
                return user_input, {
                    "intent": IntentType.request_more_info_not.value,
                    "requires_action": True,
                    "action": "request_more_info_not",
                    "needs_rag": True
                }
            elif self.state_machine.last_state == DialogState.ANSWERING:
                return user_input, {
                    "intent": IntentType.ASK_QUESTION.value,
                    "requires_action": True,
                    "action": "answer_question",
                    "needs_rag": True
                }
            else:
                return (
                    "Ok, continuo no mesmo tema.",
                    {
                        "intent": IntentType.AFFIRM.value,
                        "requires_action": False
                    }
                )

        elif current_state == DialogState.UNKNOWN:
            return user_input, {
                "intent": intent.value,
                "requires_action": True,
                "action": "unknown",
                "needs_rag": True
            }