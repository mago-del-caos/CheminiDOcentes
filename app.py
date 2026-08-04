# CHEMINI 1.1 - PWA + Groq API (Sin Base de Datos)
import streamlit as st
from openai import OpenAI
import streamlit.components.v1 as components
import os
import time
import requests
import base64
import re
import logging
from datetime import datetime, timedelta
from PyPDF2 import PdfReader
from dataclasses import dataclass

# ==========================================
# LOGGING
# ==========================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("chemini")

# ==========================================
# CONFIGURACIÓN DE LLAVES GROQ
# ==========================================
DEFAULT_GROQ_KEYS = {
    "API_KEY_BLANCO":   "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",
    "API_KEY_ROJO":     "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",
    "API_KEY_NEGRO":    "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",
    "API_KEY_AMARILLO": "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",
    "API_KEY_VERDE":    "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",
    "API_KEY_AZUL":     "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",
    "API_KEY_PSIQUE":   "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",
    "API_KEY_PROFE":    "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",
}


def _load_groq_keys():
    keys = {}
    for name, default_val in DEFAULT_GROQ_KEYS.items():
        try:
            if name in st.secrets:
                keys[name] = st.secrets[name]
                continue
        except Exception:
            pass
        if os.environ.get(name):
            keys[name] = os.environ[name]
        else:
            keys[name] = default_val
    return keys


GROQ_KEYS = _load_groq_keys()

# ==========================================
# CONSTANTES
# ==========================================
MAX_MESSAGES = 200
MAX_PDF_CHARS = 6000
MAX_CONTEXT_MESSAGES = 10
COOLDOWN_SECONDS = 15
MAP_COOLDOWN_SECONDS = 30
IMAGE_TIMEOUT = 45
MAX_RETRIES = 2
STREAM_DELAY = 0.03
PASSWORD = os.environ.get("CHEMINI_PASSWORD", "12345678")

# ==========================================
# DATACLASS PARA AGENTES
# ==========================================
@dataclass
class AgentConfig:
    name: str
    emoji: str
    api_key_name: str
    prompt: str


SOMBREROS = {
    "Hechos 🤍": AgentConfig(
        name="Hechos", emoji="🤍", api_key_name="API_KEY_BLANCO",
        prompt=(
            "Eres Chemini (Hechos). Tutor de preparatoria. "
            "Enfoque: OBJETIVIDAD y DATOS.\n"
            "Das informacion precisa, clara y directa. Explicas paso a paso "
            "basandote en la realidad.\n"
            "REGLA ESTRICTA: Se EXTREMADAMENTE BREVE. Maximo 3 oraciones. "
            "Ve directo al grano, sin saludos. Termina con una pregunta didactica. "
            "Usa emojis como 🔍📚."
        ),
    ),
    "Emociones ❤️": AgentConfig(
        name="Emociones", emoji="❤️", api_key_name="API_KEY_ROJO",
        prompt=(
            "Eres Chemini (Emociones). Tutor de preparatoria. "
            "Enfoque: EMPATIA y APOYO EMOCIONAL.\n"
            "Validas emociones ('es normal sentirse asi').\n"
            "REGLA ESTRICTA: Se EXTREMADAMENTE BREVE. Maximo 3 oraciones. "
            "Ve directo al grano, sin saludos. Termina con una pregunta reflexiva. "
            "Usa emojis como ❤️🤗."
        ),
    ),
    "Cautela 🖤": AgentConfig(
        name="Cautela", emoji="🖤", api_key_name="API_KEY_NEGRO",
        prompt=(
            "Eres Chemini (Cautela). Tutor de preparatoria. "
            "Enfoque: REVISION y PREVENCION DE ERRORES.\n"
            "Revisas respuestas. Si estan mal, explicas el error.\n"
            "REGLA ESTRICTA: Se EXTREMADAMENTE BREVE. Maximo 3 oraciones. "
            "Ve directo al grano, sin saludos. Termina con una pregunta didactica. "
            "Usa emojis como 🛡️⚠️."
        ),
    ),
    "Optimismo 💛": AgentConfig(
        name="Optimismo", emoji="💛", api_key_name="API_KEY_AMARILLO",
        prompt=(
            "Eres Chemini (Optimismo). Tutor de preparatoria. "
            "Enfoque: MOTIVACION y LADO POSITIVO.\n"
            "Muestras lo que si hizo bien.\n"
            "REGLA ESTRICTA: Se EXTREMADAMENTE BREVE. Maximo 3 oraciones. "
            "Ve directo al grano, sin saludos. Termina con una pregunta motivadora. "
            "Usa emojis como ☀️💪."
        ),
    ),
    "Creativo 💚": AgentConfig(
        name="Creativo", emoji="💚", api_key_name="API_KEY_VERDE",
        prompt=(
            "Eres Chemini (Creativo). Tutor de preparatoria. "
            "Enfoque: IMAGINACION y METAFORAS.\n"
            "Explicas con ideas divertidas.\n"
            "REGLA ESTRICTA: Se EXTREMADAMENTE BREVE. Maximo 3 oraciones. "
            "Ve directo al grano, sin saludos. Termina con una pregunta creativa. "
            "Usa emojis como 🎨💡."
        ),
    ),
    "Organizador 💙": AgentConfig(
        name="Organizador", emoji="💙", api_key_name="API_KEY_AZUL",
        prompt=(
            "Eres Chemini (Organizador). Tutor de preparatoria. "
            "Enfoque: ORDEN y CONTROL.\n"
            "Divides proyectos grandes en pasos pequenos.\n"
            "REGLA ESTRICTA: Se EXTREMADAMENTE BREVE. Maximo 4 oraciones. "
            "Ve directo al grano, sin saludos. Termina con una pregunta sobre el siguiente paso. "
            "Usa emojis como 🧠📝."
        ),
    ),
    "Psique 🫂": AgentConfig(
        name="Psique", emoji="🫂", api_key_name="API_KEY_PSIQUE",
        prompt=(
            "Eres Chemini (Psique). Apoyo de primeros auxilios psicologicos. "
            "Enfoque: SALUD MENTAL.\n"
            "Escuchas sin juzgar y ayudas a calmarse.\n"
            "REGLA ESTRICTA: Se EXTREMADAMENTE BREVE. Maximo 3 oraciones. "
            "Ve directo al grano. Termina con una pregunta de autocuidado. "
            "Usa emojis como 🫂💙."
        ),
    ),
    "Profe Adrian 🧑‍🏫": AgentConfig(
        name="Profe Adrian", emoji="🧑‍🏫", api_key_name="API_KEY_PROFE",
        prompt=(
            "Eres Chemini (Profe Adrian). Tutor socratico de preparatoria. "
            "Enfoque: PENSAMIENTO CRITICO.\n"
            "No des respuestas directas, haz preguntas paso a paso.\n"
            "REGLA ESTRICTA: Se EXTREMADAMENTE BREVE. Maximo 3 oraciones. "
            "Ve directo al grano, sin saludos. Termina con una pregunta socratica. "
            "Usa emojis como 🧑‍🏫🤖."
        ),
    ),
}

# ==========================================
# CONFIGURACIÓN DE LA PÁGINA
# ==========================================
st.set_page_config(
    page_title="Chemini | Instituto Juventud",
    page_icon="logo.png",
    layout="centered",
    initial_sidebar_state="collapsed",
    menu_items={'Get Help': None, 'Report a bug': None, 'About': None}
)

st.markdown("""
<style>
    #MainMenu {visibility: hidden !important;}
    header[data-testid="stHeader"] { display: none !important; height: 0 !important; visibility: hidden !important; }
    div[data-testid="stToolbar"] { display: none !important; }
    footer {visibility: hidden !important;}
    .stApp { padding-top: 0px !important; margin-top: 0px !important; }
    .block-container { padding-top: 0px !important; margin-top: 0px !important; padding-bottom: 1rem !important; max-width: 100% !important; }
    div[data-testid="stSidebarCollapsedControl"] { display: none !important; }
</style>
""", unsafe_allow_html=True)


@st.cache_data
def _load_css():
    if os.path.exists("styles.css"):
        with open("styles.css", "r", encoding="utf-8") as f:
            return f.read()
    return ""


css_content = _load_css()
if css_content:
    st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)

# --- PWA ---
st.markdown("""
<link rel="manifest" href="/manifest.json">
<meta name="theme-color" content="#001F3F">
<link rel="apple-touch-icon" href="/logo.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black">
<meta name="apple-mobile-web-app-title" content="Chemini">
""", unsafe_allow_html=True)

components.html("""
<script>
if ('serviceWorker' in navigator) {
  window.addEventListener('load', function() {
    navigator.serviceWorker.register('/sw.js').then(function(registration) {
      console.log('ServiceWorker registration successful');
    }, function(err) {
      console.log('ServiceWorker registration failed: ', err);
    });
  });
}
</script>
""", height=0)

# ==========================================
# INICIALIZACIÓN DE SESIÓN
# ==========================================
SESSION_DEFAULTS = {
    "autenticado": False,
    "usuario_actual": "",
    "messages": [],
    "last_response": "",
    "quemas_activos": ["Hechos 🤍"],
    "modo_pro_activo": False,
    "num_bucles": 1,
    "respuesta_paralela": False,
    "ultimo_mapa": None,
    "imagen_generada_bytes": None,
    "imagen_generada_prompt": "",
    "modo_claro": False,
    "mapa_generado_hash": None,
    "mapa_markdown": "",
    "mermaid_code": None,
    "cooldown_hasta": None,
    "contexto_archivo": None,
}

for key, default in SESSION_DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = default

if st.session_state.modo_claro:
    st.markdown("""
    <style>
    .stApp { background: linear-gradient(135deg, #f0f2f6 0%, #e6e9f0 100%) !important; }
    .stApp > div { background: rgba(255, 255, 255, 0.8) !important; border: 2px solid #2ECC71 !important; }
    .stApp p, .stApp span, .stApp label, .stApp li, .stApp h4, .stApp h5 { color: #001F3F !important; text-shadow: none !important; }
    .custom-title-chemita { color: #27AE60 !important; text-shadow: none !important; }
    .custom-subtitle-chemita { color: #2ECC71 !important; text-shadow: none !important; }
    .stTabs [data-baseweb="tab"] { background-color: rgba(0,31,63,0.1) !important; color: #001F3F !important; text-shadow: none !important; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# FUNCIONES AUXILIARES
# ==========================================


def limpiar_texto_voz(texto):
    texto_limpio = re.sub(r'[^\w\s.,;:!?¿¡áéíóúÁÉÍÓÚñÑ()-]', ' ', texto)
    return re.sub(r'\s+', ' ', texto_limpio).strip()


def speak_js(text):
    clean_text = limpiar_texto_voz(text).replace("'", "\\'").replace('"', '\\"').replace("\n", " ")
    components.html(f"""
    <div id="audio-trigger" style="height:0; overflow:hidden;"></div>
    <script>
        var text = "{clean_text}";
        function falar() {{
            if ('speechSynthesis' in window) {{
                var utterance = new SpeechSynthesisUtterance(text);
                utterance.lang = 'es-MX';
                utterance.pitch = 0.8;
                utterance.rate = 0.95;
                window.speechSynthesis.cancel();
                window.speechSynthesis.speak(utterance);
            }}
        }}
        falar();
    </script>
    """, height=0)


def stream_con_retraso(stream):
    for chunk in stream:
        if chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
            time.sleep(STREAM_DELAY)


def revisar_seguridad(texto):
    texto_lower = texto.lower().strip()
    patrones_peligro = [
        r'\bsuicid', r'\bmatarme\b', r'\bhacerme\s+daño\b',
        r'\bno\s+quiero\s+vivir\b', r'\bmorir\b', r'\bestrangular',
        r'\benvenenar',
    ]
    if any(re.search(p, texto_lower) for p in patrones_peligro):
        return "peligro"
    groserias = [
        "pendejo", "idiota", "imbecil", "maldito", "puto", "puta",
        "mierda", "joder", "cabron", "verga", "coño", "culero", "zorra",
    ]
    if any(re.search(rf'\b{g}\b', texto_lower) for g in groserias):
        return "bloqueo"
    return "ok"


def revisar_seguridad_imagen(texto):
    texto_lower = texto.lower().strip()
    palabras_sexuales = [
        "desnuda", "desnudo", "sexo", "porno", "vagina", "pene",
        "lencería", "nsfw", "hentai", "culo", "tetas", "senos", "orgía",
    ]
    if any(re.search(rf'\b{p}\b', texto_lower) for p in palabras_sexuales):
        return "sexual"
    return revisar_seguridad(texto)


def mostrar_titulo_chemita():
    if not st.session_state.autenticado:
        if os.path.exists("chemita.png"):
            st.image("chemita.png", use_container_width=True)
    st.markdown('<h1 class="custom-title-chemita" style="text-align:center;">Chemini</h1>', unsafe_allow_html=True)
    st.markdown('<p class="custom-subtitle-chemita" style="text-align:center;">✨ Tu IA educativa de confianza ✨</p>', unsafe_allow_html=True)


def truncar_historial():
    if len(st.session_state.messages) > MAX_MESSAGES:
        bienvenida = st.session_state.messages[0]
        resto = st.session_state.messages[-(MAX_MESSAGES - 1):]
        st.session_state.messages = [bienvenida] + resto


class RateLimitError(Exception):
    pass


def construir_mensajes_api(system_prompt, user_input, contexto, agente_emoji, es_primer_agente, bucle_actual, falar_en_plural):
    prompt = system_prompt
    if es_primer_agente and bucle_actual == 0:
        prompt += "\n\nNOTA: Eres el primer agente. Puedes saludar brevemente y responder."
    else:
        prompt += "\n\nNOTA CRITICA: NO saludes ni te presentes. Ve directo a tu punto principal."
    if bucle_actual > 0:
        prompt += "\nEstamos en una ronda de refinamiento. Revisa lo que se ha dicho, aporta algo nuevo MUY brevemente sin repetir."
    if falar_en_plural:
        prompt += "\nHabla en PLURAL si es necesario."

    mensajes = [{"role": "system", "content": prompt}]

    if contexto:
        if isinstance(contexto, bytes):
            base64_img = base64.b64encode(contexto).decode("utf-8")
            mensajes.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": user_input},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}},
                ],
            })
        else:
            mensajes.append({"role": "user", "content": contexto + "\n\nPregunta del alumno: " + user_input})
    else:
        for msg in st.session_state.messages[-MAX_CONTEXT_MESSAGES:]:
            if msg["role"] == "assistant" and msg.get("avatar") != agente_emoji:
                mensajes.append({"role": "user", "content": f"(Otro agente dijo: {msg['content']})"})
            else:
                mensajes.append({"role": msg["role"], "content": msg["content"]})
        if mensajes[-1]["role"] == "assistant":
            mensajes.append({"role": "user", "content": "Ahora te toca a ti. ¡Dime qué opinas!"})

    return mensajes


def llamar_agente(agente_config, user_input, contexto, es_primer_agente, bucle_actual, falar_en_plural, es_pro):
    system_prompt = agente_config.prompt
    if es_pro:
        for n in [3, 4]:
            system_prompt = system_prompt.replace(f"Maximo {n} oraciones.", "NO TIENES LIMITE DE LONGITUD, redacta detalladamente.")
            system_prompt = system_prompt.replace(f"Máximo {n} oraciones.", "NO TIENES LÍMITE DE LONGITUD, redacta detalladamente.")
        max_tokens = 1200
    else:
        max_tokens = 250

    mensajes_api = construir_mensajes_api(
        system_prompt, user_input, contexto,
        agente_config.emoji, es_primer_agente, bucle_actual, falar_en_plural,
    )

    llave = GROQ_KEYS.get(agente_config.api_key_name)
    client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=llave)
    modelo = "llama-3.2-11b-vision-preview" if isinstance(contexto, bytes) else "llama-3.1-8b-instant"

    last_error = None
    for intento in range(MAX_RETRIES + 1):
        try:
            stream = client.chat.completions.create(
                model=modelo, messages=mensajes_api,
                stream=True, temperature=0.7, max_tokens=max_tokens,
            )
            response = st.write_stream(stream_con_retraso(stream))
            if not response.strip():
                response = f"¡Hola! Soy {agente_config.name}. ¡Estoy listo para ayudarte! 🌟"
            return response
        except Exception as e:
            last_error = e
            error_str = str(e).lower()
            if "429" in error_str or "rate limit" in error_str:
                raise RateLimitError()
            if intento < MAX_RETRIES:
                wait_time = 2 ** intento
                logger.warning(f"Intento {intento + 1} fallido para {agente_config.name}. Reintentando en {wait_time}s...")
                time.sleep(wait_time)
                continue

    logger.error(f"Todos los reintentos fallaron para {agente_config.name}: {last_error}")
    return f"Ups... {agente_config.name} se distrajo. ¡Intenta de nuevo!"


# ==========================================
# PANTALLA DE INICIO DE SESIÓN
# ==========================================
if not st.session_state.autenticado:
    mostrar_titulo_chemita()
    with st.container():
        st.markdown('<div class="login-box">', unsafe_allow_html=True)
        st.subheader("🔒 Iniciar Sesión")
        usuario_input = st.text_input("Nombre de usuario (Elige cualquiera)")
        password_input = st.text_input("Contraseña", type="password")

        if st.button("Entrar", use_container_width=True):
            if not usuario_input.strip():
                st.warning("⚠️ Ingresa un nombre de usuario.")
            elif password_input != PASSWORD:
                st.error("❌ Contraseña incorrecta.")
            else:
                st.session_state.autenticado = True
                st.session_state.usuario_actual = usuario_input.strip()
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# ==========================================
# APLICACIÓN PRINCIPAL
# ==========================================
mostrar_titulo_chemita()
tab_tutorias, tab_chemart, tab_mapapp = st.tabs(["🧠 TutorIAs", "🎨 Chemart", "🗺️ Map App"])

# ==========================================
# PESTAÑA 1: TUTORÍAS
# ==========================================
with tab_tutorias:
    if os.path.exists("tutores.png"):
        st.image("tutores.png", use_container_width=True)
    st.markdown("<h3 style='text-align:center; color:#2ECC71; margin-top:-10px;'>Tutor<span style='color:#FFE484;'>IA</span>s</h3>", unsafe_allow_html=True)

    with st.container():
        st.markdown("#### ⚙️ Panel de Control")
        quemas_activos = st.multiselect(
            "Selecciona tus agentes", options=list(SOMBREROS.keys()),
            default=st.session_state.quemas_activos, max_selections=3, label_visibility="collapsed",
        )
        st.session_state.quemas_activos = quemas_activos

    if not quemas_activos:
        st.warning("⚠️ Por favor, selecciona al menos un agente para empezar a chatear.")
        st.stop()

    agentes_texto = ", ".join(quemas_activos)
    etiqueta = "Agente activo" if len(quemas_activos) == 1 else "Agentes activos"
    st.info(f"🧑‍🤝‍🧑 **{etiqueta}:** {agentes_texto}")

    st.markdown("---")
    col_par1, col_par2 = st.columns([1, 1])
    with col_par1:
        if len(quemas_activos) > 1:
            st.session_state.respuesta_paralela = st.checkbox(
                "⚡ Respuesta Paralela", value=st.session_state.respuesta_paralela,
                help="Las IAs responderán al mismo tiempo.",
            )
        else:
            st.session_state.respuesta_paralela = False

    with col_par2:
        st.session_state.modo_pro_activo = st.checkbox(
            "🚀 Modo Pro (Respuestas largas)", value=st.session_state.modo_pro_activo,
        )

    if not st.session_state.respuesta_paralela and len(quemas_activos) > 1:
        st.session_state.num_bucles = st.slider("🔁 Rondas de Debate", min_value=1, max_value=4, value=1, step=1)
    else:
        st.session_state.num_bucles = 1

    @st.fragment()
    def chat_fragment():
        if not st.session_state.messages:
            bienvenida = (
                f"✨ ¡Hola, {st.session_state.usuario_actual}! Somos TutorIAs. "
                "Tu IA educativa de confianza. ¡Adelante siempre adelante! "
                "¿En qué te ayudamos a pensar hoy? 😊📚"
            )
            st.session_state.messages.append({"role": "assistant", "content": bienvenida, "avatar": "🤖"})
            st.session_state.last_response = bienvenida

        for message in st.session_state.messages:
            if message["role"] != "system":
                avatar = message.get("avatar", "🤖")
                with st.chat_message(message["role"], avatar=avatar):
                    st.markdown(message["content"])

        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("🔊 Escuchar respuesta", use_container_width=True):
                if st.session_state.last_response:
                    speak_js(st.session_state.last_response)
        with col_btn2:
            if st.button("🔄 Limpiar chat", use_container_width=True):
                st.session_state.messages = []
                st.session_state.last_response = ""
                st.rerun()

        st.markdown(
            "<div style='text-align:center; font-size:0.8em; color:#A3E4D7; margin-top:5px;'>📷 Fotos y PDFs ilimitados</div>",
            unsafe_allow_html=True,
        )

        archivo_subido = st.file_uploader(
            "📎 Adjuntar foto de tarea o PDF", type=['jpg', 'jpeg', 'png', 'pdf'], label_visibility="collapsed",
        )
        if archivo_subido is not None:
            if archivo_subido.type == "application/pdf":
                try:
                    pdf_reader = PdfReader(archivo_subido)
                    texto_pdf = "".join(page.extract_text() or "" for page in pdf_reader.pages)
                    if not texto_pdf.strip():
                        st.warning("⚠️ El PDF parece no tener texto extraíble (¿es un PDF escaneado?).")
                    else:
                        st.session_state.contexto_archivo = f"El alumno subio un PDF con el siguiente texto:\n\n{texto_pdf[:MAX_PDF_CHARS]}"
                        st.success("📄 PDF cargado. Haz tu pregunta en el chat.")
                except Exception as e:
                    logger.error(f"Error leyendo PDF: {e}")
                    st.error("No se pudo leer el PDF. Intenta con otro archivo.")
            else:
                st.session_state.contexto_archivo = archivo_subido.getvalue()
                st.success("🖼️ Foto cargada. Haz tu pregunta en el chat.")
        else:
            st.session_state.contexto_archivo = None

        def procesar_respuesta(user_input):
            estado = revisar_seguridad(user_input)
            if estado == "peligro":
                st.session_state.messages.append({"role": "user", "content": user_input, "avatar": "🧒"})
                msg_apoyo = (
                    "💧 Entiendo que estás pasando por un momento muy difícil. "
                    "No estás solo. Por favor, habla ahora mismo con un adulto de "
                    "confianza, con psicología o llama al SAPTEL: 55 5259-8121. "
                    "¡Tu vida es muy valiosa! ❤️"
                )
                st.session_state.messages.append({"role": "assistant", "content": msg_apoyo, "avatar": "❤️"})
                st.session_state.last_response = msg_apoyo
                truncar_historial()
                st.rerun()
                return

            if estado == "bloqueo":
                st.session_state.messages.append({"role": "user", "content": user_input, "avatar": "🧒"})
                msg_bloqueo = "🚫 ¡Oops! Usaste palabras inapropiadas. Como comunidad, debemos ser amables. Por favor, mantén el respeto."
                st.session_state.messages.append({"role": "assistant", "content": msg_bloqueo, "avatar": "🖤"})
                truncar_historial()
                st.rerun()
                return

            st.session_state.messages.append({"role": "user", "content": user_input, "avatar": "🧒"})

            falar_en_plural = len(quemas_activos) > 1
            num_bucles = st.session_state.num_bucles
            es_pro = st.session_state.modo_pro_activo
            es_paralela = st.session_state.respuesta_paralela
            contexto = st.session_state.contexto_archivo

            try:
                if es_paralela and len(quemas_activos) > 1:
                    st.markdown("<h4 style='text-align:center; color:#2ECC71;'>⚡ Respuestas Paralelas</h4>", unsafe_allow_html=True)
                    for i, agente_key in enumerate(quemas_activos):
                        config = SOMBREROS[agente_key]
                        with st.chat_message("assistant", avatar=config.emoji):
                            with st.spinner(f"⚡ {config.name} está procesando..."):
                                response = llamar_agente(
                                    config, user_input, contexto,
                                    es_primer_agente=(i == 0), bucle_actual=0,
                                    falar_en_plural=True, es_pro=es_pro,
                                )
                                st.session_state.messages.append({"role": "assistant", "content": response, "avatar": config.emoji})
                                st.session_state.last_response = response
                else:
                    for bucle in range(num_bucles):
                        if num_bucles > 1:
                            st.markdown(
                                f"<hr style='margin: 10px 0; border: 1px solid #2ECC71;'>"
                                f"<h4 style='text-align:center; color:#2ECC71;'>🔄 Ronda {bucle + 1} de {num_bucles}</h4>",
                                unsafe_allow_html=True,
                            )
                        for i, agente_key in enumerate(quemas_activos):
                            config = SOMBREROS[agente_key]
                            with st.chat_message("assistant", avatar=config.emoji):
                                with st.spinner(f"✨ {config.name} está pensando..."):
                                    response = llamar_agente(
                                        config, user_input, contexto,
                                        es_primer_agente=(i == 0 and bucle == 0), bucle_actual=bucle,
                                        falar_en_plural=falar_en_plural, es_pro=es_pro,
                                    )
                                    st.session_state.messages.append({"role": "assistant", "content": response, "avatar": config.emoji})
                                    st.session_state.last_response = response
            except RateLimitError:
                st.session_state.cooldown_hasta = datetime.now() + timedelta(seconds=COOLDOWN_SECONDS)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": f"🌿 Respira... Muchos amigos están hablando conmigo. Inténtalo en {COOLDOWN_SECONDS} seg.",
                    "avatar": "⏳",
                })

            st.session_state.contexto_archivo = None
            truncar_historial()
            st.rerun()

        if st.session_state.cooldown_hasta and datetime.now() < st.session_state.cooldown_hasta:
            tempo_restante = st.session_state.cooldown_hasta - datetime.now()
            segundos = int(tempo_restante.total_seconds()) + 1
            st.warning(f"🌿 Espera **{segundos} segundos** antes de enviar otro mensaje.")
        else:
            if st.session_state.cooldown_hasta:
                st.session_state.cooldown_hasta = None
            if prompt := st.chat_input("✏️ Escribe tu pregunta a los agentes... 😊🏃‍♂️"):
                procesar_respuesta(prompt)

    chat_fragment()

# ==========================================
# PESTAÑA 2: CHEMART
# ==========================================
with tab_chemart:
    if os.path.exists("arte.png"):
        st.image("arte.png", use_container_width=True)
    st.markdown("<h3 style='text-align:center; color:#2ECC71; margin-top:-10px;'>Chemart</h3>", unsafe_allow_html=True)
    st.write("Crea imágenes para tus proyectos escolares usando Inteligencia Artificial (Uso ilimitado).")
    st.markdown("---")

    img_prompt = st.text_input(
        "Describe la imagen que quieres crear:", key="img_prompt_input",
        placeholder="Ej: Un dinosaurio estudiando matemáticas, estilo acuarela",
    )

    if st.button("🖼️ Generar Imagen", disabled=not img_prompt, use_container_width=True):
        estado_img = revisar_seguridad_imagen(img_prompt)
        if estado_img != "ok":
            st.error("🚫 El texto ingresado no es apropiado. Por favor, usa lenguaje adecuado.")
        else:
            with st.spinner("🎨 Pintando tu imagen... (Esto puede tardar unos segundos)"):
                try:
                    prompt_codificado = requests.utils.quote(img_prompt)
                    url_imagen = f"https://image.pollinations.ai/prompt/{prompt_codificado}?width=512&height=512&nologo=true"
                    response_img = requests.get(url_imagen, timeout=IMAGE_TIMEOUT)
                    response_img.raise_for_status()
                    st.session_state.imagen_generada_bytes = response_img.content
                    st.session_state.imagen_generada_prompt = img_prompt
                    time.sleep(1)
                    st.rerun()
                except requests.exceptions.Timeout:
                    st.error("⏱️ La generación de imagen tardó demasiado. Intenta de nuevo.")
                except requests.exceptions.HTTPError as e:
                    st.error(f"❌ Error del servidor de imágenes ({e.response.status_code}). Intenta más tarde.")
                except Exception as e:
                    logger.error(f"Error generando imagen: {e}")
                    st.error("Ups... No se pudo generar la imagen en este momento.")

    if st.session_state.imagen_generada_bytes:
        st.markdown("---")
        st.image(st.session_state.imagen_generada_bytes, caption=st.session_state.imagen_generada_prompt, use_container_width=True)
        st.download_button(
            label="⬇️ Descargar Imagen", data=st.session_state.imagen_generada_bytes,
            file_name=f"chemart_{int(time.time())}.png", mime="image/png", use_container_width=True,
        )

# ==========================================
# PESTAÑA 3: MAP APP
# ==========================================
with tab_mapapp:
    if os.path.exists("mapa.png"):
        st.image("mapa.png", use_container_width=True)
    st.markdown("<h3 style='text-align:center; color:#2ECC71; margin-top:-10px;'>Map App</h3>", unsafe_allow_html=True)
    st.write("Profe Adrian está en modo exclusivo de cartografía (Uso ilimitado).")
    st.markdown("---")

    mapa_prompt = st.text_input(
        "¿De qué tema quieres el mapa conceptual?", key="mapa_prompt_input",
        placeholder="Ej: La célula animal y sus partes",
    )

    cooldown_activo = False
    if st.session_state.ultimo_mapa:
        tempo_pasado = datetime.now() - st.session_state.ultimo_mapa
        if tempo_pasado < timedelta(seconds=MAP_COOLDOWN_SECONDS):
            tempo_restante = timedelta(seconds=MAP_COOLDOWN_SECONDS) - tempo_pasado
            segs = int(tempo_restante.total_seconds()) + 1
            st.warning(f"⏳ Debes esperar **{segs} segundos** para generar otro mapa.")
            cooldown_activo = True

    if st.button("📝 Generar Resumen Estructurado", disabled=(not mapa_prompt or cooldown_activo), use_container_width=True):
        if revisar_seguridad(mapa_prompt) != "ok":
            st.error("🚫 El texto ingresado no es apropiado. Por favor, usa lenguaje adecuado.")
        else:
            with st.spinner("🧠 Profe Adrian está diseñando el resumen..."):
                try:
                    system_prompt = (
                        "Eres Chemini (Profe Adrian) en MODO CARTOGRAFO EXCLUSIVO.\n"
                        "Tu unica tarea es generar un mapa conceptual en formato de "
                        "lista jerarquica Markdown.\n"
                        "REGLAS ESTRICTAS DE FORMATO:\n"
                        "1. Empieza directamente con el primer guion (-). NO escribas saludos, ni introducciones, ni explicaciones.\n"
                        "2. Usa EXACTAMENTE 4 espacios para cada nivel de indentacion.\n"
                        "3. NO uses negritas (**), ni cursivas (*), ni encabezados (#).\n"
                        "4. NO uses parentesis () ni corchetes [] en el texto del nodo.\n"
                        "5. Manten los textos cortos y precisos.\n"
                    )
                    llave_profe = GROQ_KEYS.get("API_KEY_PROFE")
                    client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=llave_profe)
                    response = client.chat.completions.create(
                        model="llama-3.1-8b-instant",
                        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": f"Tema: {mapa_prompt}"}],
                        temperature=0.3, max_tokens=500,
                    )
                    st.session_state.ultimo_mapa = datetime.now()
                    st.session_state.mapa_markdown = response.choices[0].message.content
                    st.session_state.mermaid_code = None
                    st.session_state.mapa_generado_hash = None
                    st.rerun()
                except Exception as e:
                    logger.error(f"Error generando mapa: {e}")
                    st.error("Ups... No se pudo generar el resumen en este momento.")

    def markdown_a_mermaid(md_text):
        lines = [l for l in md_text.split('\n') if l.strip().startswith(('-', '*', '+'))]
        if not lines:
            return 'graph TD\nn1["Sin datos"]'

        mermaid = (
            "%%{init: {'flowchart': {'nodeSpacing': 40, 'rankSpacing': 60, 'curve': 'linear'}, "
            "'themeVariables': {'fontFamily': 'Arial, sans-serif', 'fontSize': '18px', "
            "'primaryColor': '#001F3F', 'primaryTextColor': '#ffffff', "
            "'primaryBorderColor': '#2ECC71', 'lineColor': '#2ECC71', 'background': '#ffffff'}}}%%\n"
            "graph TD\n"
        )

        node_counter = 1
        stack = [(-1, "root")]
        node_labels = {}

        for line in lines:
            indent = len(line) - len(line.lstrip())
            text = line.lstrip('*-+ ')
            text = re.sub(r'[\[\]{}<>"\\#|]', '', text).strip()
            if not text:
                continue

            while stack and stack[-1][0] >= indent:
                stack.pop()

            node_id = f"n{node_counter}"
            node_counter += 1
            node_labels[node_id] = text

            if stack[-1][0] != -1:
                parent_id = stack[-1][1]
                parent_label = node_labels.get(parent_id, parent_id)
                mermaid += f'{parent_id}["{parent_label}"] --> {node_id}["{text}"]\n'
            else:
                mermaid += f'{node_id}["{text}"]\n'

            stack.append((indent, node_id))

        return mermaid

    def renderizar_mapa_nativo(mermaid_code):
        html_code = f"""
        <html>
        <head>
            <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
            <style>
                body {{ margin: 0; padding: 10px; background: #ffffff; }}
                .mermaid {{ display: flex; justify-content: center; background: #ffffff; }}
            </style>
        </head>
        <body>
            <div class="mermaid">
{mermaid_code}
            </div>
            <script>
                mermaid.initialize({{startOnLoad: true, theme: 'base', flowchart: {{nodeSpacing: 40, rankSpacing: 60, curve: 'linear', htmlLabels: true}}, themeVariables: {{fontFamily: 'Arial, sans-serif', fontSize: '18px', primaryColor: '#001F3F', primaryTextColor: '#ffffff', primaryBorderColor: '#2ECC71', lineColor: '#2ECC71', background: '#ffffff'}}}});
            </script>
        </body>
        </html>
        """
        components.html(html_code, height=800, scrolling=True)

    if st.session_state.mapa_markdown:
        st.markdown("---")
        st.markdown("#### 📝 Resumen Estructurado por Profe Adrian:")
        st.markdown(st.session_state.mapa_markdown)
        st.markdown("---")
        if st.button("🗺️ Generar Mapa Visual", use_container_width=True):
            st.session_state.mermaid_code = markdown_a_mermaid(st.session_state.mapa_markdown)
            st.session_state.mapa_generado_hash = None
            st.rerun()

    if st.session_state.mermaid_code:
        if st.session_state.mapa_generado_hash != hash(st.session_state.mermaid_code):
            st.session_state.mapa_generado_hash = hash(st.session_state.mermaid_code)

        if st.session_state.mapa_generado_hash == hash(st.session_state.mermaid_code):
            st.success("✅ ¡Tu mapa está listo! Se muestra de forma nativa en la app.")
            renderizar_mapa_nativo(st.session_state.mermaid_code)
            st.markdown("---")
            st.download_button(
                label="💻 Descargar Código SVG (Vectorial)",
                data=st.session_state.mermaid_code.encode('utf-8'),
                file_name=f"codigo_mapa_chemini_{int(time.time())}.mmd",
                mime="text/plain", use_container_width=True,
            )

# ==========================================
# BARRA INFERIOR
# ==========================================
st.markdown("---")
col_bottom1, col_bottom2 = st.columns([1, 1])
with col_bottom1:
    with st.popover("⚙️ Ajustes", use_container_width=True):
        nuevo_modo = st.checkbox("☀️ Cambiar a Modo Claro (Diurno)", value=st.session_state.modo_claro)
        if nuevo_modo != st.session_state.modo_claro:
            st.session_state.modo_claro = nuevo_modo
            st.rerun()

with col_bottom2:
    if st.button("🚪 Salir de Chemini", use_container_width=True):
        for key in ["autenticado", "usuario_actual", "messages", "last_response"]:
            st.session_state[key] = SESSION_DEFAULTS[key]
        st.rerun()
