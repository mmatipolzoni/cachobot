# 🤖 CachoBot - Bot de Discord con música, moderación e IA

Este es un bot de Discord desarrollado como proyecto personal, con funcionalidades integradas de música (YouTube y Spotify), moderación de servidores y un sistema de chat potenciado por OpenAI (ChatGPT). Ideal para aprender sobre APIs, asincronismo en Python y comandos slash.

## 🚀 Funcionalidades principales

🎵 Reproducción de música
- Reproduce canciones desde YouTube o links de Spotify (track, playlist, álbum)
- Comandos slash para facilidad de uso
- Autoplay basado en canciones relacionadas

🛡️ Moderación
- Comandos "/ban", "/kick", "/mute"
- Revisión de permisos antes de ejecutar acciones
- Rol "Muteado" para silenciar usuarios

🧠 ChatGPT integrado
- IA que responde en canales específicos
- Contexto por canal (historial limitado)
- Personalidad argentina relajada y con humor 😎

⚙️ Extras
- Cambio de presencia del bot cada 10 segundos
- Comando "/reset_contexto" para borrar el historial del chat IA
- Auto-apagado diario a las 3:00 AM (puede desactivarse)

## 📦 Tecnologías utilizadas

- Python 3.10
- [discord.py](https://discordpy.readthedocs.io/)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [Spotipy](https://spotipy.readthedocs.io/)
- [OpenAI Python SDK](https://platform.openai.com/)
- "python-dotenv" para manejo seguro de credenciales