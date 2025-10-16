// URL da API (ajuste se necessário)
const API_URL = "http://127.0.0.1:5000";
const CONVERSATION_EXPIRATION_MS = 1; //3600000
// Variáveis globais para manter o histórico e o nome do arquivo da conversa atual
let conversationHistory = [];
let conversation_id = null;
let isHistoryVisible = false;

// Variáveis para speech-to-text
let mediaRecorder = null;
let audioChunks = [];
let isRecording = false;
let stream = null;

// Variáveis para text-to-speech
let ttsEnabled = true;
let isTtsPaused = false;
let currentUtterance = null;

let ttsRate = 1.0;
let currentUtteranceText = "";
let currentCharIndex = 0;

//Estado do chat
let lastBotResponse = "";

// Função para salvar estado da conversa
async function saveConversationState() {
  try {
    const state = {
      conversationHistory,
      conversation_id,
      timestamp: Date.now()
    };
    
    await chrome.storage.local.set({ 
      currentConversation: state,
      lastActivity: Date.now()
    });
    
    console.log("Estado da conversa salvo:", state);
  } catch (error) {
    console.error("Erro ao salvar estado:", error);
  }
}

// Função para carregar estado da conversa
async function loadConversationState() {
  try {
    const result = await chrome.storage.local.get(['currentConversation', 'lastActivity']);
    
    if (result.currentConversation) {
      const state = result.currentConversation;
      const timeSinceLastActivity = Date.now() - (result.lastActivity || 0);
      
      // Se passou menos de 1 hora desde a última atividade, restaura a conversa
      if (timeSinceLastActivity < CONVERSATION_EXPIRATION_MS) { // 60000
        conversationHistory = state.conversationHistory || [];
        conversation_id = state.conversation_id;
        
        console.log("Estado da conversa carregado:", state);
        return true;
      } else {
        // Limpa conversas antigas
        await chrome.storage.local.remove(['currentConversation']);
        console.log("Conversa expirada, iniciando nova");
      }
    }
    
    return false;
  } catch (error) {
    console.error("Erro ao carregar estado:", error);
    return false;
  }
}

// Função para restaurar mensagens na UI
function restoreMessagesInUI() {
  const conversationDiv = document.getElementById("conversation");
  conversationDiv.innerHTML = ""; // Limpa o chat
  
  if (conversationHistory && conversationHistory.length > 0) {
    conversationHistory.forEach(message => {
      const role = message.role === "user" ? "user" : "bot";
      const content = message.parts ? message.parts[0] : message.content;
      addMessage(role, content);
    });
    
    // Mostra os controles da conversa
    showConversationControls();
    
    // Habilita o botão de envio
    document.getElementById("sendButton").disabled = false;
  }
}

// Função para mostrar controles da conversa
function showConversationControls() {
  //const startButton = document.getElementById("startBotButton");
  const sendButton = document.getElementById("sendButton");
  const newConversationButton = document.getElementById("newConversationButton");
  const loadHistoryButton = document.getElementById("loadHistoryButton");
  const voiceButton = document.getElementById("voiceButton");
  //const ttsButton = document.getElementById("TTSButton");

  //startButton.style.display = "none";
  document.getElementById("conversation").style.display = "block";
  document.getElementById("userInput").style.display = "block";
  document.getElementById("historico").style.display = "block";
  document.getElementById("TTSWrapper").style.display = "inline-flex";
  
  sendButton.style.display = "inline-block";
  newConversationButton.style.display = "inline-block";
  loadHistoryButton.style.display = "inline-block";
  voiceButton.style.display = "inline-block";
  //ttsButton.style.display = "inline-block";
}

// Função para exibir a mensagem
function addMessage(role, message) {
  const conversationDiv = document.getElementById("conversation");

  // Criar elemento da mensagem
  const messageDiv = document.createElement("div");
  messageDiv.classList.add("message", role);
  messageDiv.innerHTML = message
  .replace(/\n/g, '<br>')                          // Quebras de linha
  .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>') // **negrito**
  .replace(/\*(.*?)\*/g, '<em>$1</em>')            // *itálico*
  .replace(/`(.*?)`/g, '<code>$1</code>')          // `código`
  .replace(/\\u([0-9a-fA-F]{4})/g, (match, code) => // Fix unicode (\u00ea -> ê)
    String.fromCharCode(parseInt(code, 16)));

  // Adicionar ao chat
  conversationDiv.appendChild(messageDiv);
  
  // Scroll automático para a última mensagem
  conversationDiv.scrollTop = conversationDiv.scrollHeight;
  
  // Salva o estado após adicionar mensagem
  saveConversationState();
}
let botStarted = false;
// Função para iniciar o bot (extraída do event listener original)
async function startBot() {
  if (botStarted) {
    console.log("⚠️ Bot já foi iniciado — ignorando nova execução duplicada.");
    return;
  }
  botStarted = true; // marca como iniciado

  const filenameToClear = "block_freq";
  showConversationControls();

  let [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  let url = tab.url;

  try {
    await fetch(`${API_URL}/clear_block_freq`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename: filenameToClear }),
    });
    console.log("🧹 Ficheiro apagado com sucesso.");
  } catch (error) {
    console.error("❌ Erro ao apagar ficheiro:", error);
  }

  try {
    const response = await fetch(`${API_URL}/scrape`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });

    const data = await response.json();
    if (data.conversation_id) {
      conversation_id = data.conversation_id;
      addMessage("bot", "Olá. Como posso ajudar?");
      speakText("Conversa pronta a ser iniciada.");
      document.getElementById("sendButton").disabled = false;


      await saveConversationState();
    } else {
      addMessage("bot", "Erro ao iniciar a conversa.");
    }
  } catch (error) {
    console.error("❌ Erro ao enviar URL:", error);
    addMessage("bot", "Erro ao conectar com o servidor.");
  }
}





// Função para iniciar gravação de áudio
async function startRecording() {
  try {
    console.log("Iniciando gravação...");
    speakText("Iniciando gravação");
    // Solicitar permissão para usar microfone
    stream = await navigator.mediaDevices.getUserMedia({ 
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
        sampleRate: 44100
      } 
    });

    // Criar MediaRecorder
    mediaRecorder = new MediaRecorder(stream, {
      mimeType: 'audio/webm;codecs=opus'
    });

    audioChunks = [];

    mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        audioChunks.push(event.data);
      }
    };

    mediaRecorder.onstop = async () => {
      console.log("Gravação terminada, processando áudio...");
      
      // Criar blob do áudio
      const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
      
      // Converter para texto
      await processAudioToText(audioBlob);
      
      // Limpar stream
      if (stream) {
        stream.getTracks().forEach(track => track.stop());
        stream = null;
      }
    };

    mediaRecorder.start();
    isRecording = true;
    
    updateVoiceButton();
    await saveSessionState();
    
  } catch (error) {
    console.error("Erro ao iniciar gravação:", error);
    addMessage("bot", "Erro ao acessar microfone. Verifique as permissões.");
    
    // Reset estado
    isRecording = false;
    updateVoiceButton();
  }
}

// Função para parar gravação
function stopRecording() {
  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    console.log("Parando gravação...");
    mediaRecorder.stop();
    isRecording = false;
    updateVoiceButton();
    speakText("Processando");
    saveSessionState();
  }
}

// Função para atualizar botão de voz
function updateVoiceButton() {
  const voiceButton = document.getElementById("voiceButton");
  const voiceIcon = voiceButton.querySelector(".voice-icon");
  const voiceText = voiceButton.querySelector(".voice-text");
  
  if (isRecording) {
    voiceButton.classList.add("recording");
    voiceIcon.textContent = "⏹️";
    voiceText.textContent = "Parar";
    voiceButton.title = "Parar gravação";
  } else {
    voiceButton.classList.remove("recording");
    voiceIcon.textContent = "🎤";
    voiceText.textContent = "Gravar";
    voiceButton.title = "Gravar áudio";
  }
}

// Função para processar áudio e converter para texto
async function processAudioToText(audioBlob) {
  if (!conversation_id) {
    addMessage("bot", "Erro: Nenhuma conversa ativa.");
    return;
  }

  try {
    console.log("Enviando áudio para conversão...");
    
    // Mostrar indicador de processamento
    const voiceButton = document.getElementById("voiceButton");
    const voiceIcon = voiceButton.querySelector(".voice-icon");
    const voiceText = voiceButton.querySelector(".voice-text");
    
    voiceButton.disabled = true;
    voiceIcon.textContent = "⏳";
    voiceText.textContent = "Processando...";

    // Criar FormData para enviar o áudio
    const formData = new FormData();
    formData.append('audio', audioBlob, 'audio.webm');
    formData.append('conversation_id', conversation_id);
    formData.append('language', 'pt'); // Português por padrão

    // Enviar para o endpoint speech-to-text
    const response = await fetch(`${API_URL}/STT`, {
      method: 'POST',
      body: formData
    });

    const data = await response.json();

    if (data.error) {
      addMessage("bot", `Erro: ${data.error}`);
      return;
    }

    // Exibir texto transcrito
    if (data.transcribed_text) {
      addMessage("user", data.transcribed_text);
    }

    // Exibir resposta do bot
    if (data.response) {
      addMessage("bot", data.response);
      lastBotResponse = data.response;
      speakText(data.response);
    }

    // Atualizar estado da conversa
    if (data.conversation_history) {
      conversationHistory = data.conversation_history;
    }

    // Salvar estado
    await saveConversationState();

    console.log("Áudio processado com sucesso!");

  } catch (error) {
    console.error("Erro ao processar áudio:", error);
    addMessage("bot", "Erro ao processar áudio. Tente novamente.");
  } finally {
    // Restaurar botão de voz
    const voiceButton = document.getElementById("voiceButton");
    voiceButton.disabled = false;
    updateVoiceButton();
  }
}


//----Estado da sessão----
async function saveSessionState() {
  try {
    const sessionState = {
      ttsEnabled,
      ttsRate,
      isTtsPaused,
      isRecording,
      conversation_id,
      lastBotResponse,
    };
    await chrome.storage.local.set({ sessionState });
    console.log("Sessão salva:", sessionState);
  } catch (error) {
    console.error("Erro ao salvar sessão:", error);
  }
}

async function loadSessionState() {
  try {
    const result = await chrome.storage.local.get("sessionState");
    if (result.sessionState) {
      const state = result.sessionState;
      ttsEnabled = state.ttsEnabled ?? true;
      ttsRate = state.ttsRate ?? 1.0;
      isTtsPaused = state.isTtsPaused ?? false;
      isRecording = state.isRecording ?? false;
      conversation_id = state.conversation_id ?? null;
      lastBotResponse = state.lastBotResponse ?? "";
      console.log("Sessão restaurada:", state);
      return true;
    }
    return false;
  } catch (error) {
    console.error("Erro ao carregar sessão:", error);
    return false;
  }
}
//--------

document.addEventListener("DOMContentLoaded", async () => {
  const startButton = document.getElementById("startBotButton");
  const sendButton = document.getElementById("sendButton");
  const inputField = document.getElementById("userInput");
  const voiceButton = document.getElementById("voiceButton");
  const pauseResumeButton = document.getElementById("pauseResumeTTSButton");

  sendButton.disabled = true;
  if (startButton) startButton.style.display = "none";
  await loadSessionState()
  
  // Primeiro, tenta carregar uma conversa existente
  const hasExistingConversation = await loadConversationState();
  
    
  if (hasExistingConversation) {
    console.log("Conversa existente encontrada — restaurando...");
    restoreMessagesInUI();
    showConversationControls(); // mostra UI completa
  } else {
    console.log("Nenhuma conversa encontrada — iniciando nova...");
    await startBot();
  }

  // Atualizar UI baseado no estado carregado
  updateToggleState();
  updateVoiceButton();

  // Verificar se deve iniciar automaticamente (via atalho)
  //chrome.storage.local.get(['autoStartBot'], (result) => {
  //  if (result.autoStartBot) {
  //    console.log("Auto-iniciando bot via atalho global...");
  //    // Limpar a flag
  //    chrome.storage.local.remove(['autoStartBot']);
  //    
  //    // Se não há conversa existente, inicia nova
  //    if (!hasExistingConversation) {
  //      setTimeout(() => {
  //        startBot();
  //      }, 100);
  //    }
  //  }
  //});
  chrome.storage.local.get(['autoStartBot'], async (result) => {
  if (result.autoStartBot) {
    console.log("Auto-iniciando bot via atalho global...");
    await chrome.storage.local.remove(['autoStartBot']);

    if (!hasExistingConversation) {
      const res = await chrome.storage.local.get("lastActivity");
      const timeSinceLastActivity = Date.now() - (res.lastActivity || 0);

      if (timeSinceLastActivity >= CONVERSATION_EXPIRATION_MS ) {
        setTimeout(() => {
          startBot();
        }, 100);
      } else {
        console.log("Conversa ainda válida, não vou criar nova.");
        restoreMessagesInUI();
      }
    }
  }
  });

  let [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  let url = tab.url;

  // Enviar msg com Enter
  if (inputField && sendButton) {
    inputField.addEventListener("keydown", function (event) {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        if (!sendButton.disabled) {
          sendButton.click();
        }
      }
    });
  }

  // Event listener para botão de voz
  if (voiceButton) {
    voiceButton.addEventListener("click", () => {
      if (isRecording) {
        stopRecording();
      } else {
        startRecording();
      }
    });
  }

  let spaceKeyTimer = null;
  let isSpaceHeld = false;

  document.addEventListener("keydown", (event) => {
    if (event.code === "Space" && !isSpaceHeld && !event.repeat) {
      isSpaceHeld = true;
      spaceKeyTimer = setTimeout(() => {
        if (isSpaceHeld && !isRecording) {
          startRecording();
        }
      }, 1000); // segundos
    }

    if (event.code === "ArrowRight" && !event.repeat) {
      if (ttsRate < 2.0) {
        ttsRate = 2.0;
        console.log(`Acelerando TTS: ${ttsRate}x`);

        if (window.speechSynthesis.speaking && currentUtteranceText) {
          const remainingText = currentUtteranceText.slice(currentCharIndex);
          window.speechSynthesis.cancel();
          speakText(remainingText);
        }
      }
    }

    if (event.code === "KeyP" && event.altKey && !event.repeat) {
      const pauseResumeButton = document.getElementById("pauseResumeTTSButton");

      if (!window.speechSynthesis.speaking) return;

      if (!isTtsPaused) {
        window.speechSynthesis.pause();
        isTtsPaused = true;
        pauseResumeButton.textContent = "▶️ Retomar";
        pauseResumeButton.title = "Retomar leitura";
      } else {
        window.speechSynthesis.resume();
        isTtsPaused = false;
        pauseResumeButton.textContent = "⏸️ Pausar";
        pauseResumeButton.title = "Pausar leitura";
      }
    }
    //const ttsWrapper = document.getElementById("TTSWrapper");
    ttsWrapper.addEventListener("keydown", (event) => {
      // Permite ativar/desativar com Enter ou Espaço quando o elemento está focado
      if (event.code === "Enter" || event.code === "Space") {
        event.preventDefault(); // Previne scroll da página com Space
        ttsWrapper.click(); // Simula o click que já existe
      }
    });

    if (event.code === "KeyT" && event.altKey && !event.repeat) {
      if (ttsEnabled) {
        // Para qualquer fala atual primeiro
        window.speechSynthesis.cancel();

        // Esconde o botão de pausar/retomar
        const pauseResumeButton = document.getElementById("pauseResumeTTSButton");
        pauseResumeButton.style.display = "none";

        // Limpa o estado atual
        currentUtteranceText = "";
        currentCharIndex = 0;
        isTtsPaused = false;

        // Fala "TTS desativado" e depois desativa
        const utterance = new SpeechSynthesisUtterance("TTS desativado");
        utterance.lang = 'pt-PT';
        utterance.onend = () => {
          ttsEnabled = false;
          updateToggleState();
          console.log("TTS desativado via atalho após mensagem");
        };
        window.speechSynthesis.speak(utterance);
      } else {
        // TTS foi ativado
        ttsEnabled = true;
        updateToggleState();
        speakText("TTS ativado");
        console.log("TTS ativado via atalho");
        saveSessionState();
      }
  }
  

    if (event.code === "KeyN" && event.altKey && !event.repeat) {
      const newButton = document.getElementById("newConversationButton");
      if (newButton && !newButton.disabled) {
          newButton.click();
      }
    }

    if (event.code === "KeyH" && event.altKey && !event.repeat) {
      const historyButton = document.getElementById("loadHistoryButton");
      if (historyButton) {
        historyButton.click();
      }
    }
  }); 

  document.addEventListener("keyup", (event) => {
    if (event.code === "Space") {
      clearTimeout(spaceKeyTimer);
      if (isRecording) {
        stopRecording();
      }
      isSpaceHeld = false;
    }
    if (event.code === "ArrowRight") {
    ttsRate = 1.0;
    console.log(`Velocidade do TTS restaurada: ${ttsRate}x`);

    if (window.speechSynthesis.speaking && currentUtteranceText) {
      const remainingText = currentUtteranceText.slice(currentCharIndex);
      window.speechSynthesis.cancel();
      speakText(remainingText);
    }
  }
  });

  pauseResumeButton.addEventListener("click", () => {
    //event.stopPropagation();
    if (!window.speechSynthesis.speaking) return;
  
    if (!isTtsPaused) {
      window.speechSynthesis.pause();
      isTtsPaused = true;
      pauseResumeButton.textContent = "▶️ Retomar";
      pauseResumeButton.title = "Retomar leitura";
    } else {
      window.speechSynthesis.resume();
      isTtsPaused = false;
      pauseResumeButton.textContent = "⏸️ Pausar";
      pauseResumeButton.title = "Pausar leitura";
    }
  });

  // Auto-salvar quando a extensão for fechada
  window.addEventListener('beforeunload', () => {
    saveConversationState();
    saveSessionState();
    
    // Parar gravação se estiver ativa
    if (isRecording) {
      stopRecording();
    }
  });
});

// Event listener do botão de iniciar
//document.getElementById("startBotButton").addEventListener("click", startBot);

// Auto-resize do textarea
document.getElementById("userInput").addEventListener("input", function () {
  this.style.height = "40px";
  this.style.height = this.scrollHeight + "px";
});


function speakText(text, lang = 'pt-PT') {
  if (!ttsEnabled || !text) return;

  const pauseResumeButton = document.getElementById("pauseResumeTTSButton");

  // Armazena o texto e reinicia estado
  currentUtteranceText = text;
  currentCharIndex = 0;
  isTtsPaused = false;

  // Cancela qualquer fala anterior
  window.speechSynthesis.cancel();

  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = lang;
  utterance.rate = ttsRate;
  utterance.pitch = 1;

  pauseResumeButton.style.display = "inline-block";
  pauseResumeButton.textContent = "⏸️ Pausar";
  pauseResumeButton.title = "Pausar leitura";

  // Captura a posição atual (índice de caractere)
  utterance.onboundary = (event) => {
    if (event.name === "word") {
      currentCharIndex = event.charIndex;
    }
  };

  utterance.onend = () => {
    pauseResumeButton.style.display = "none";
    currentUtteranceText = "";
    currentCharIndex = 0;
  };

  currentUtterance = utterance;
  window.speechSynthesis.speak(utterance);
  saveSessionState();
}

const ttsWrapper = document.getElementById("TTSWrapper");
const slider = document.getElementById("slider");

function updateToggleState() {
  const slider = document.getElementById("slider");
    if (ttsEnabled) {
        slider.classList.add("active");
    } else {
        slider.classList.remove("active");
    }
}


ttsWrapper.addEventListener("click", () => {
  ttsEnabled = !ttsEnabled;
  
  if (!ttsEnabled) {
    // TTS foi desativado
    if (window.speechSynthesis.speaking) {
      window.speechSynthesis.cancel();
      console.log("TTS parado ao desativar");

    }

    // Esconde o botão de pausar/retomar
    const pauseResumeButton = document.getElementById("pauseResumeTTSButton");
    pauseResumeButton.style.display = "none";
    
    // Limpa o estado atual
    currentUtteranceText = "";
    currentCharIndex = 0;
    isTtsPaused = false;
    
    const utterance = new SpeechSynthesisUtterance("TTS desativado");
    utterance.lang = 'pt-PT';
    utterance.onend = () => {
      ttsEnabled = false;
      isTtsPaused = false;
      window.speechSynthesis.cancel();
      updateToggleState();
      console.log("TTS desativado");
    };
    window.speechSynthesis.speak(utterance);
  } else {
    // TTS foi ativado
    console.log("TTS ativado");
    speakText("TTS ativado");
  }
  
  updateToggleState();
  saveSessionState();
});

//ttsWrapper.addEventListener("click", () => {
//  ttsEnabled = !ttsEnabled;
//    
//  if (!ttsEnabled && window.speechSynthesis.speaking) {
//      window.speechSynthesis.cancel();
//      console.log("TTS parado ao desativar");
//      speakText("TTS desativo");
//    }
//    console.log(`TTS ${ttsEnabled ? "ativado" : "desligado"}`);
//    updateToggleState();
//    speakText("TTS ativado"); 
//});
//updateToggleState();


// Envio de mensagem
document.getElementById("sendButton").addEventListener("click", async () => {
  const sendButton = document.getElementById("sendButton");
  const defaultText = sendButton.querySelector(".default-text");
  const loadingText = sendButton.querySelector(".loading-text");
  const userInputField = document.getElementById("userInput");
  const user_input = userInputField.value.trim();
  
  if (!user_input) return;

  userInputField.value = "";
  userInputField.style.height = "auto";

  sendButton.disabled = true;
  defaultText.classList.add("hidden");
  loadingText.classList.remove("hidden");

  // Exibe a mensagem do usuário
  addMessage('user', user_input);

  // Captura o contexto da homepage
  const homepageContextElement = document.getElementById("homepageContext");
  const homepage_context = homepageContextElement ? homepageContextElement.innerText : "";

  if (!conversation_id) {
    console.warn("conversation_id não definido! Pode gerar novo vetor.");
  }

  const payload = {
    user_input: user_input,
    conversation_history: conversationHistory,
    homepage_context: homepage_context,
    conversation_id: conversation_id
  };

  try {
    const response = await fetch(`${API_URL}/send_message`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    const data = await response.json();
    if (data.error) {
      addMessage('bot', `Erro: ${data.error}`);
      return;
    }

    // Atualiza as variáveis globais
    conversationHistory = data.conversation_history;
    conversation_id = data.conversation_id;

    // Exibe a resposta do bot
    addMessage('bot', data.response);
    lastBotResponse = data.response;
    speakText(data.response);
    
    // Salva o estado atualizado
    await saveConversationState();
    await saveSessionState();

  } catch (error) {
    addMessage('bot', `Erro: ${error}`);
  } finally {
    sendButton.disabled = false;
    defaultText.classList.remove("hidden");
    loadingText.classList.add("hidden");
  }
});

// Nova conversa
document.getElementById("newConversationButton").addEventListener("click", async () => {
  const filenameToClear = "block_freq";
  const sendButton = document.getElementById("sendButton");
  const newConversationButton = document.getElementById("newConversationButton");
  const defaultText = newConversationButton.querySelector(".default-text");
  const loadingText = newConversationButton.querySelector(".loading-text");
  

  newConversationButton.disabled = true;
  sendButton.disabled = true;
  defaultText.classList.add("hidden");
  loadingText.classList.remove("hidden");

  // Parar gravação se estiver ativa
  if (isRecording) {
    stopRecording();
  }

  // Limpa o estado salvo
  await chrome.storage.local.remove(['currentConversation']);

  try {
    await fetch(`${API_URL}/clear_block_freq`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename: filenameToClear })
    });
    console.log("Ficheiro apagado com sucesso.");
  } catch (error) {
    console.error("Erro ao apagar ficheiro:", error);
  }

  document.getElementById("conversation").innerHTML = "";
  conversationHistory = [];
  conversation_id = null;

  let [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const url = tab.url;

  try {
    const response = await fetch(`${API_URL}/scrape`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url })
    });
    
    const data = await response.json();
    if (data.error) {
      addMessage("bot", `Erro: ${data.error}`);
      return;
    }

    conversation_id = data.conversation_id;
    console.log("Nova conversa iniciada:", conversation_id);
    addMessage("bot", "Nova conversa iniciada");
    
    sendButton.disabled = false;
    
    // Salva o novo estado
    await saveConversationState();
    speakText("Nova conversa iniciada");
  } catch (error) {
    addMessage("bot", `Erro: ${error}`);
  } finally {
    // Restaurar o estado normal do botão
    newConversationButton.disabled = false;
    defaultText.classList.remove("hidden");
    loadingText.classList.add("hidden");
  }
});

// Histórico
document.getElementById("loadHistoryButton").addEventListener("click", async () => {
  const historyDiv = document.getElementById("history");

  if (isHistoryVisible) {
    historyDiv.style.display = "none";
    document.getElementById("loadHistoryButton").textContent = "Mostrar Histórico";
  } else {
    historyDiv.style.display = "block";
    document.getElementById("loadHistoryButton").textContent = "Ocultar Histórico";

    try {
      const response = await fetch(`${API_URL}/conversations`);
      const data = await response.json();
      historyDiv.innerHTML = ""; 

      if (data.conversations && data.conversations.length > 0) {
        data.conversations.forEach((conv, index) => {
          const item = document.createElement("div");
          item.className = "history-item";
          item.setAttribute("role", "listitem");
          
          // Criar botão para o título/nome da conversa (em vez de span)
          const titleButton = document.createElement("button");
          titleButton.textContent = conv.title || conv.id;
          titleButton.className = "history-title";
          titleButton.setAttribute("aria-label", `Carregar conversa: ${conv.title || conv.id}`);
          titleButton.setAttribute("tabindex", 12 + (index * 2)); // Tabindex dinâmico
          titleButton.addEventListener("click", () => loadConversation(conv.id));
          
          // Adicionar navegação por teclado para o título
          titleButton.addEventListener("keydown", (event) => {
            if (event.code === "Enter" || event.code === "Space") {
              event.preventDefault();
              loadConversation(conv.id);
            }
          });
          
          // Criar botão de delete
          const deleteBtn = document.createElement("button");
          deleteBtn.textContent = "✖";
          deleteBtn.className = "delete-btn";
          deleteBtn.setAttribute("aria-label", `Apagar conversa: ${conv.title || conv.id}`);
          deleteBtn.setAttribute("tabindex", 13 + (index * 2)); // Tabindex dinâmico
          deleteBtn.title = "Apagar conversa";
          deleteBtn.addEventListener("click", (e) => {
            e.stopPropagation();
            deleteConversation(conv.id, item);
          });
          
          // Adicionar navegação por teclado para o botão delete
          deleteBtn.addEventListener("keydown", (event) => {
            if (event.code === "Enter" || event.code === "Space") {
              event.preventDefault();
              event.stopPropagation();
              deleteConversation(conv.id, item);
            }
          });
          
          item.appendChild(titleButton);
          item.appendChild(deleteBtn);
          historyDiv.appendChild(item);
        });
      } else {
        const emptyMessage = document.createElement("p");
        emptyMessage.textContent = "Nenhuma conversa encontrada";
        emptyMessage.setAttribute("role", "status");
        emptyMessage.setAttribute("aria-live", "polite");
        historyDiv.appendChild(emptyMessage);
      }
    } catch (error) {
      const errorMessage = document.createElement("p");
      errorMessage.textContent = "Erro ao carregar o histórico: " + error;
      errorMessage.setAttribute("role", "alert");
      errorMessage.setAttribute("aria-live", "assertive");
      historyDiv.appendChild(errorMessage);
    }
  }

  isHistoryVisible = !isHistoryVisible;
});


// Nova função para apagar conversas
async function deleteConversation(conversationId, itemElement) {
  // Confirmar antes de apagar
  if (!confirm(`Tem certeza que deseja apagar esta conversa?`)) {
    return;
  }
  
  try {
    const response = await fetch(`${API_URL}/conversation/${conversationId}`, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json'
      }
    });
    
    const data = await response.json();
    
    if (response.ok) {
      // Remove o item da UI
      itemElement.remove();
      
      // Se a conversa apagada é a atual, limpa a conversa atual
      const cleanId = conversationId.replace('.json', '');
      if (conversation_id === cleanId) {
        // Limpa a conversa atual
        document.getElementById("conversation").innerHTML = "";
        conversationHistory = [];
        conversation_id = null;
        
        // Parar gravação se estiver ativa
        if (isRecording) {
          stopRecording();
        }
        
        // Limpa o estado salvo
        await chrome.storage.local.remove(['currentConversation']);
        
        // Esconde os controles da conversa e mostra o botão de iniciar
        //const startButton = document.getElementById("startBotButton");
        const sendButton = document.getElementById("sendButton");
        const newConversationButton = document.getElementById("newConversationButton");
        const loadHistoryButton = document.getElementById("loadHistoryButton");
        const voiceButton = document.getElementById("voiceButton");
        
        //startButton.style.display = "block";
        document.getElementById("conversation").style.display = "none";
        document.getElementById("userInput").style.display = "none";
        document.getElementById("historico").style.display = "none";
        
        sendButton.style.display = "none";
        newConversationButton.style.display = "none";
        loadHistoryButton.style.display = "none";
        voiceButton.style.display = "none";
        sendButton.disabled = true;
      }
      
      console.log("Conversa apagada com sucesso");
    } else {
      alert(`Erro ao apagar conversa: ${data.error || 'Erro desconhecido'}`);
    }
    
  } catch (error) {
    console.error("Erro ao apagar conversa:", error);
    alert("Erro ao conectar com o servidor para apagar a conversa");
  }
}

// Função para carregar conversa do histórico
async function loadConversation(filename) {
  try {
    const response = await fetch(`${API_URL}/conversation/${filename}`);
    const data = await response.json();
    if (data.error) {
      alert("Erro: " + data.error);
      return;
    }
    
    const conv = data.conversation;
    const retrievedInfo = data.retrieved_info || ""; 

    console.log("Contexto recuperado:", retrievedInfo);

    conversationHistory = conv;
    conversation_id = filename.replace(/\.json$/, "");
    console.log("conversation_id carregado:", conversation_id);

    // Restaura as mensagens na UI
    const conversationDiv = document.getElementById("conversation");
    conversationDiv.innerHTML = ""; 

    conv.forEach(message => {
      const role = message.role === "user" ? "user" : "bot";
      addMessage(role, message.parts[0]);
    });

    // Salva o estado da conversa carregada
    await saveConversationState();

  } catch (error) {
    alert("Erro ao carregar a conversa: " + error);
  }
}

document.querySelector(".close-btn").addEventListener("click", () => {
  // Parar gravação se estiver ativa
  if (isRecording) {
    stopRecording();
  }
  
  // Salva antes de fechar
  saveConversationState();
  window.close();
});