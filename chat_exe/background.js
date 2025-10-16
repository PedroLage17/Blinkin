// Background script para gerenciar comandos globais
chrome.commands.onCommand.addListener(async (command) => {
  if (command === "start_bot") {
    console.log("🎯 Comando Alt+A detectado");
    
    try {
      // Define a flag de autoinício
      await chrome.storage.local.set({ autoStartBot: true });
      console.log("✅ Flag autoStartBot definida");
      
      // Abre o popup
      await chrome.action.openPopup();
      console.log("✅ Popup aberto");
    } catch (error) {
      console.error("❌ Erro ao processar comando:", error);
    }
  }
});

// Log quando o service worker inicia
console.log("🚀 Service Worker carregado");

//// Background script para gerenciar comandos globais
//let shouldStartBot = false;
//chrome.commands.onCommand.addListener((command) => {
//  if (command === "start_bot") {
//
//    shouldStartBot = true;
//
//    chrome.action.openPopup(); // abre popup da extensão
//  }
//});
//
//// Background script para gerenciar comandos globais
//chrome.commands.onCommand.addListener(async (command) => {
//  if (command === "start_bot") {
//    // Define a flag de autoinício
//    await chrome.storage.local.set({ autoStartBot: true });
//    // Abre o popup
//    chrome.action.openPopup();
//  }
//});


//chrome.commands.onCommand.addListener((command) => {
//  console.log('Comando recebido:', command);
//  
//  if (command === 'start_bot') {
//    // Abre o popup e sinaliza para iniciar o bot automaticamente
//    chrome.storage.local.set({ autoStartBot: true }, () => {
//      // Abre o popup da extensão
//      chrome.action.openPopup();
//    });
//  }
//});

// Listener para quando a extensão é aberta via atalho _execute_action
//chrome.action.onClicked.addListener(() => {
//  // Define flag para auto-iniciar quando o popup abrir
//  chrome.storage.local.set({ autoStartBot: true });
//});