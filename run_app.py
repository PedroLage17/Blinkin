from Blinkin import app
import sys
import signal


def shutdown(*_):
    print("\n🛑 Encerrando servidor Flask...")
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    try:
        
        print("🚀 A iniciar servidor...")
        print("📍 URL: http://127.0.0.1:5000")
        print("⚠️ Para parar o servidor, pressione Ctrl+C, ou feche está janela\n")
        
        app.run(
            host="127.0.0.1",
            port=5000,
            debug=False,  
            use_reloader=False
        )
        
    except KeyboardInterrupt:
        print("\n\nServidor parado pelo utilizador")
        sys.exit(0)
    
