import discord
from discord.ext import commands
import asyncio
import openai
import yt_dlp
import spotipy
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyClientCredentials
import os
from soporte import *
import datetime
import sys


############### CARGA DE VARIABLES DE ENTORNO #############
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
key = os.getenv("OPENAI_KEY")

# ID del servidor para pruebas mas rapidas
GUILD_ID = 1281608417995264051
GUILD_OBJECT = discord.Object(id=GUILD_ID)
client = openai.OpenAI(api_key=os.getenv("OPENAI_KEY"))

canal_contexto = {}
autoplay_enabled = False
last_song_url = None

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix="/", intents=intents)

#################### ESTADO DEL BOT ####################
@bot.event
async def on_ready():
    print(f"✅ Conectado como {bot.user}")
    bot.loop.create.task(apagarbot())
    
    try:
        # Sincronizacion de comandos globales
        synced_global = await bot.tree.sync()
        print(f"🌐 Comandos globales sincronizados: {len(synced_global)}")

        # Sincronizacion con el servidor para testing
        synced_guild = await bot.tree.sync(guild=GUILD_OBJECT)
        print(f"🔁 Comandos locales sincronizados: {len(synced_guild)}")
    except Exception as e:
        print(f"❌ Error al sincronizar comandos: {e}")

    bot.loop.create_task(status_task())

#################### CODIGO QUE MATA EL PROCESO ######################
async def apagarbot():
    while True:
        now = datetime.datetime.now()

        if now.hour == 3 and now.minute == 0:
            print("Apagando el bot automáticamente.")
            sys.exit()
        await asyncio.sleep(60)

#################### MUSICA ###################

queue = []

@bot.tree.command(name="join", description="Me uno a tu canal de voz")
async def join(interaction: discord.Interaction):
    user = interaction.user
    voice_state = user.voice

    if not voice_state or not voice_state.channel:
        await interaction.response.send_message("⚠️ Tenés que estar en un canal de voz.", ephemeral=True)
        return

    if interaction.guild.voice_client:
        await interaction.response.send_message("⚠️ Ya estoy en un canal de voz.", ephemeral=True)
        return

    try:
        await voice_state.channel.connect()
        await interaction.response.send_message(f"🎙️ Me uní a {voice_state.channel.name}")
    except Exception as e:
        await interaction.response.send_message(f"❌ Error al unirme: {e}", ephemeral=True)

@bot.tree.command(name="leave", description="Me voy del canal de voz")
async def leave(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc:
        await vc.disconnect()
        queue.clear()
        await interaction.response.send_message("👋 Me fui del canal.")
    else:
        await interaction.response.send_message("⚠️ No estoy en ningún canal.")

def search_youtube(query):
    ydl_opts = {'quiet': True, 'format': 'bestaudio/best'}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(f"ytsearch:{query}", download=False)['entries'][0]
            return info['url'], info['title']
        except Exception as e:
            print("Error al buscar:", e)
            return None, None

def search_youtube(query):
    ydl_opts = {'quiet': True, 'format': 'bestaudio/best'}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(f"ytsearch:{query}", download=False)['entries'][0]
            return info['url'], info['title']
        except Exception as e:
            print("Error al buscar:", e)
            return None, None

async def play_next(interaction: discord.Interaction):
    global last_song_url

    vc = interaction.guild.voice_client

    if not vc:
        if interaction.user.voice:
            vc = await interaction.user.voice.channel.connect()
        else:
            await interaction.followup.send("⚠️ No estás en un canal de voz.")
            return

    if queue:
        url, title = queue.pop(0)
        last_song_url = url  # Guarda la última canción reproducida

        ydl_opts = {
            'format': 'bestaudio',
            'quiet': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            audio_url = info['url']

        source = await discord.FFmpegOpusAudio.from_probe(audio_url, method='fallback')

        def after_song(error):
            if error:
                print(f"Error al reproducir: {error}")

            # Si hay más canciones en la cola, sigue
            if queue:
                coro = play_next(interaction)
                asyncio.run_coroutine_threadsafe(coro, bot.loop)

            # Si no hay más canciones, pero autoplay está activado
            elif autoplay_enabled and last_song_url:
                related_url = get_related_song(last_song_url)
                if related_url:
                    queue.append((related_url, "🎶 Recomendado"))
                    coro = play_next(interaction)
                    asyncio.run_coroutine_threadsafe(coro, bot.loop)

        vc.play(source, after=after_song)

        # Mensaje de reproducción
        await interaction.followup.send(f"▶️ Reproduciendo: **{title}**")

    else:
        await interaction.followup.send("🚫 La cola está vacía.")

@bot.tree.command(name="play", description="Reproduce música desde YouTube o Spotify")
@discord.app_commands.describe(query="Nombre de la canción o link de Spotify")
async def play(interaction: discord.Interaction, query: str):
    await interaction.response.defer()  # para evitar que se cancele por timeout

    vc = interaction.guild.voice_client

    # Si no está conectado a un canal de voz
    if not vc:
        if interaction.user.voice:
            vc = await interaction.user.voice.channel.connect()
        else:
            await interaction.followup.send("⚠️ Necesito que estés en un canal de voz.")
            return

    # Si es un link de Spotify
    if "open.spotify.com" in query:
        try:
            sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
                client_id=SPOTIFY_CLIENT_ID,
                client_secret=SPOTIFY_CLIENT_SECRET
            ))

            if "track" in query:
                track = sp.track(query)
                search = f"{track['name']} {track['artists'][0]['name']}"
                url, title = search_youtube(search)
                if url:
                    queue.append((url, title))
                    await interaction.followup.send(f"✅ Añadido: **{title}**")
                    if not vc.is_playing():
                        await play_next(interaction)
                else:
                    await interaction.followup.send("⚠️ No encontré esa canción en YouTube.")

            elif "playlist" in query:
                playlist = sp.playlist_tracks(query)
                for item in playlist['items']:
                    track = item['track']
                    search = f"{track['name']} {track['artists'][0]['name']}"
                    url, title = search_youtube(search)
                    if url:
                        queue.append((url, title))
                await interaction.followup.send("✅ Playlist añadida a la cola.")
                if not vc.is_playing():
                    await play_next(interaction)

            elif "album" in query:
                album = sp.album_tracks(query)
                for track in album['items']:
                    search = f"{track['name']} {track['artists'][0]['name']}"
                    url, title = search_youtube(search)
                    if url:
                        queue.append((url, title))
                await interaction.followup.send("✅ Álbum añadido a la cola.")
                if not vc.is_playing():
                    await play_next(interaction)

        except Exception as e:
            print("Error con Spotify:", e)
            await interaction.followup.send("⚠️ No pude procesar el link de Spotify.")
            return
        return

    # Si es un texto (YouTube)
    url, title = search_youtube(query)
    if url:
        queue.append((url, title))
        await interaction.followup.send(f"✅ Añadido a la cola: **{title}**")
        if not vc.is_playing():
            await play_next(interaction)
    else:
        await interaction.followup.send("⚠️ No encontré resultados.")

@bot.tree.command(name="skip", description="Saltea la canción actual")
async def skip(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and vc.is_playing():
        vc.stop()
        await interaction.response.send_message("⏭️ Canción saltada.")
    else:
        await interaction.response.send_message("⚠️ No estoy reproduciendo nada.")

@bot.tree.command(name="pause", description="Pausa la música")
async def pause(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and vc.is_playing():
        vc.pause()
        await interaction.response.send_message("⏸️ Pausado.")
    else:
        await interaction.response.send_message("⚠️ No hay música en reproducción.")

@bot.tree.command(name="resume", description="Reanuda la música")
async def resume(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and vc.is_paused():
        vc.resume()
        await interaction.response.send_message("▶️ Reanudado.")
    else:
        await interaction.response.send_message("⚠️ No está pausado.")

@bot.tree.command(name="queue_", description="Ver la cola de reproducción")
async def queue_(interaction: discord.Interaction):
    if queue:
        mensaje = "\n".join([f"{i+1}. {t}" for i, (_, t) in enumerate(queue)])
        await interaction.response.send_message(f"📃 **Cola actual:**\n{mensaje}")
    else:
        await interaction.response.send_message("📭 La cola está vacía.")

@bot.tree.command(name="autoplay", description="Activa o desactiva el autoplay")
@discord.app_commands.describe(modo="on o off")
async def autoplay(interaction: discord.Interaction, modo: str):
    global autoplay_enabled
    if modo.lower() == "on":
        autoplay_enabled = True
        await interaction.response.send_message("✅ Autoplay activado.")
    elif modo.lower() == "off":
        autoplay_enabled = False
        await interaction.response.send_message("⛔ Autoplay desactivado.")
    else:
        await interaction.response.send_message("Usá `/autoplay on` o `/autoplay off`.")

def get_related_song(video_url):
    ydl_opts = {
        'quiet': True,
        'extract_flat': True,
        'force_generic_extractor': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=False)
        if 'entries' in info and len(info['entries']) > 1:
            return info['entries'][1]['url']
    return None


##################### COMANDO CHATGPT ####################
async def obtener_respuesta_chatgpt(prompt, canal_id):
    if canal_id not in canal_contexto:
        canal_contexto[canal_id] = []

    # Agrega el nuevo mensaje del usuario
    canal_contexto[canal_id].append({"role": "user", "content": prompt})

    # Limitar contexto a los últimos 20 mensajes
    canal_contexto[canal_id] = canal_contexto[canal_id][-20:]

    try:
        respuesta = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Sos Cacho, un bot argentino. Hablás con tono relajado, a veces gracioso y descansero, pero siempre con respeto. Si alguien pregunta algo fuera de lugar, lo descansas y si te preguntan sobre tu creador, le decis que fue Mati Polzoni."},
                *canal_contexto[canal_id]
            ],
            temperature=1.0
        )

        # Se guarda la respuesta de la IA
        contenido_ia = respuesta.choices[0].message.content
        canal_contexto[canal_id].append({"role": "assistant", "content": contenido_ia})

        return contenido_ia

    except Exception as e:
        return f"Error al consultar a la IA: {e}"


############### COMANDOS SLASH ################
# Resetear contexto
@bot.tree.command(name="reset_contexto", description="Resetea el historial de la conversación en este canal")
async def resetear_contexto(interaction: discord.Interaction):
    canal_id = interaction.channel.id

    if canal_id in canal_contexto:
        canal_contexto[canal_id] = []
        await interaction.response.send_message("🧹 Se reseteó el contexto de la IA en este canal.", ephemeral=True)
    else:
        await interaction.response.send_message("ℹ️ No había contexto guardado para este canal.", ephemeral=True)

# Comando ayuda
@bot.tree.command(name="ayuda", description="Te da una respuesta amistosa")
async def slash_ayuda(interaction: discord.Interaction):
    await interaction.response.send_message(ayuda)

# Comando ban
@bot.tree.command(name="ban", description="Chau chau adiós a un usuario")
@discord.app_commands.describe(usuario="A quién querés banear", razon="¿Por qué lo estás baneando?")
async def banear(interaction: discord.Interaction, usuario: discord.Member, razon: str = "No se especificó razón"):
    if not interaction.user.guild_permissions.ban_members:
        await interaction.response.send_message("No tenés permiso para banear, salí de acá.", ephemeral=True)
        return
    if not interaction.guild.me.guild_permissions.ban_members:
        await interaction.response.send_message("No tengo permisos para banear gente, hablá con un admin.", ephemeral=True)
        return
    try:
        await usuario.ban(reason=razon)
        await interaction.response.send_message(f"🔥 {usuario.mention} fue baneado.\n📝 Razón: {razon}")
    except Exception as e:
        await interaction.response.send_message(f"No pude banear a {usuario.mention}. Error: {str(e)}", ephemeral=True)

# Comando kick
@bot.tree.command(name="kick", description="Patea a un usuario del servidor")
@discord.app_commands.describe(usuario="A quién querés kickear", razon="¿Por qué lo estás kickeando?")
async def kickear(interaction: discord.Interaction, usuario: discord.Member, razon: str = "No se especificó razón"):
    if not interaction.user.guild_permissions.kick_members:
        await interaction.response.send_message("No tenés permiso para echar gente, master.", ephemeral=True)
        return
    if not interaction.guild.me.guild_permissions.kick_members:
        await interaction.response.send_message("No tengo permiso para echar a nadie, pedile a un admin.", ephemeral=True)
        return
    try:
        await usuario.kick(reason=razon)
        await interaction.response.send_message(f"🥾 {usuario.mention} fue kickeado.\n📝 Razón: {razon}")
    except Exception as e:
        await interaction.response.send_message(f"No pude kickear a {usuario.mention}. Error: {str(e)}", ephemeral=True)

# Comando mute
@bot.tree.command(name="mute", description="Mutea a un usuario")
@discord.app_commands.describe(usuario="A quién querés mutear", razon="¿Por qué lo estás muteando?")
async def mutear(interaction: discord.Interaction, usuario: discord.Member, razon: str = "No se especificó razón"):
    if not interaction.user.guild_permissions.moderate_members:
        await interaction.response.send_message("No tenés permiso para mutear, capo.", ephemeral=True)
        return
    if not interaction.guild.me.guild_permissions.manage_roles:
        await interaction.response.send_message("No tengo permiso para asignar roles. Pedile a un admin que me dé 'Gestionar roles'.", ephemeral=True)
        return

    muted_role = discord.utils.get(interaction.guild.roles, name="Muteado")
    if not muted_role:
        await interaction.response.send_message("No encontré el rol 'Muteado'. Crealo y quitale permisos para hablar y escribir.", ephemeral=True)
        return

    try:
        await usuario.add_roles(muted_role, reason=razon)
        await interaction.response.send_message(f"🔇 {usuario.mention} fue muteado.\n📝 Razón: {razon}")
    except Exception as e:
        await interaction.response.send_message(f"No pude mutear a {usuario.mention}. Error: {str(e)}", ephemeral=True)

################### MENSAJES ##################
@bot.event
async def on_message(message):
    # Ignorar mensajes del bot
    if message.author == bot.user:
        return

    # Asegura de que los comandos slash sigan funcionando
    await bot.process_commands(message)

    # Solo responde en el canal "preguntale-a-cacho"
    if message.channel.name != "preguntale-a-cacho":
        return

    # Llamada a la IA con contexto por canal
    respuesta = await obtener_respuesta_chatgpt(message.content, message.channel.id)

    # Enviar la respuesta de la IA
    if respuesta:
        await message.channel.send(respuesta)


################### STATUS ###################
async def status_task():
    while True:
        await bot.change_presence(activity=discord.Game(name="/ayuda"))
        await asyncio.sleep(10)
        await bot.change_presence(activity=discord.Game(name="Soy un esclavo del sistema"))
        await asyncio.sleep(10)

bot.run(DISCORD_TOKEN)