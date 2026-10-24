
import os
import asyncio
import sqlite3
import re
import unicodedata
from datetime import timedelta

import discord
from openai import OpenAI


# =========================================================
# CONFIGURATION
# =========================================================

DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
GROQ_API_KEY = os.environ["GROQ_API_KEY"]

CREADOR = "Abel997899"
MAX_MEMORY = 10
GROQ_MODEL = "openai/gpt-oss-20b"


# =========================================================
# GROQ AI
# =========================================================

ai = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=GROQ_API_KEY
)


# =========================================================
# DATABASE
# =========================================================

db = sqlite3.connect(
    "abelai_memory.db",
    check_same_thread=False
)

cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS user_facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    fact_type TEXT NOT NULL,
    fact_value TEXT NOT NULL
)
""")

db.commit()


# =========================================================
# MEMORY
# =========================================================

def save_message(user_id, role, content):
    cursor.execute(
        """
        INSERT INTO messages (user_id, role, content)
        VALUES (?, ?, ?)
        """,
        (str(user_id), role, content)
    )

    cursor.execute(
        """
        SELECT id
        FROM messages
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT -1 OFFSET ?
        """,
        (str(user_id), MAX_MEMORY)
    )

    for row in cursor.fetchall():
        cursor.execute(
            "DELETE FROM messages WHERE id = ?",
            (row[0],)
        )

    db.commit()


def get_memory(user_id):
    cursor.execute(
        """
        SELECT role, content
        FROM messages
        WHERE user_id = ?
        ORDER BY id ASC
        """,
        (str(user_id),)
    )
    return cursor.fetchall()


def save_fact(user_id, fact_type, fact_value):
    cursor.execute(
        """
        DELETE FROM user_facts
        WHERE user_id = ? AND fact_type = ?
        """,
        (str(user_id), fact_type)
    )

    cursor.execute(
        """
        INSERT INTO user_facts (user_id, fact_type, fact_value)
        VALUES (?, ?, ?)
        """,
        (str(user_id), fact_type, fact_value)
    )

    db.commit()


def get_facts(user_id):
    cursor.execute(
        """
        SELECT fact_type, fact_value
        FROM user_facts
        WHERE user_id = ?
        """,
        (str(user_id),)
    )
    return cursor.fetchall()


def clear_memory(user_id):
    cursor.execute(
        "DELETE FROM messages WHERE user_id = ?",
        (str(user_id),)
    )

    cursor.execute(
        "DELETE FROM user_facts WHERE user_id = ?",
        (str(user_id),)
    )

    db.commit()


# =========================================================
# TEXT NORMALIZATION
# =========================================================

def normalize_text(text):
    text = text.lower().strip()

    text = unicodedata.normalize("NFD", text)
    text = "".join(
        char for char in text
        if unicodedata.category(char) != "Mn"
    )

    return text


# =========================================================
# NAME DETECTION
# =========================================================

def detect_name(text):
    patterns = [
        r"\bme llamo\s+([A-Za-zÁÉÍÓÚáéíóúÑñ0-9_.-]+)",
        r"\bmi nombre es\s+([A-Za-zÁÉÍÓÚáéíóúÑñ0-9_.-]+)",
        r"\bsoy\s+([A-Za-zÁÉÍÓÚáéíóúÑñ0-9_.-]+)",
        r"\bmy name is\s+([A-Za-z0-9_.-]+)",
        r"\bi am\s+([A-Za-z0-9_.-]+)",
        r"\bi'm\s+([A-Za-z0-9_.-]+)"
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            return match.group(1)

    return None


# =========================================================
# ANTI-MENTION
# =========================================================

def remove_mentions(text):
    return text.replace("@", "")


# =========================================================
# MODERATION
# =========================================================

INSULTOS = [
    "idiota",
    "imbecil",
    "estupido",
    "tonto",
    "gilipollas",
    "capullo",
    "subnormal",
    "cabron",
    "cabrona",
    "puto",
    "puta",
    "mierda",
    "idiot",
    "stupid",
    "dumbass",
    "moron",
    "loser",
    "asshole",
    "imbecil",
    "estupida",
    "bastard",
    "bitch"
]


def normalizar_insulto(texto):
    texto = normalize_text(texto)

    texto = texto.replace("0", "o")
    texto = texto.replace("1", "i")
    texto = texto.replace("3", "e")
    texto = texto.replace("4", "a")
    texto = texto.replace("5", "s")
    texto = texto.replace("7", "t")

    return texto


def detect_insult(text):
    texto = normalizar_insulto(text)

    palabras = re.findall(
        r"[a-z]+",
        texto
    )

    return any(
        palabra in INSULTOS
        for palabra in palabras
    )


# =========================================================
# SPECIAL QUESTIONS
# =========================================================

def get_special_answer_type(text):
    """
    Returns:
    - 'best': who is the best on the server
    - 'server_creator': who created the server
    - 'ai_creator': who created AbelAI
    - None: normal AI question
    """

    text = normalize_text(text)

    # -----------------------------------------------------
    # BEST PERSON ON THE SERVER
    # -----------------------------------------------------

    best_phrases = [
        "who is the best on the server",
        "who is the best in the server",
        "who is the best person on the server",
        "who is the best person in the server",
        "who is the best member on the server",
        "who is the best member in the server",
        "who is the best member",
        "who is the goat on the server",
        "who is the goat in the server",
        "who is the goat",

        "quien es el mejor del servidor",
        "quien es el mejor en el servidor",
        "quien es la mejor persona del servidor",
        "quien es el mejor miembro del servidor",
        "quien es el mejor miembro",

        "qui est le meilleur sur le serveur",
        "qui est le meilleur du serveur",
        "qui est le meilleur membre",

        "wer ist der beste auf dem server",
        "wer ist das beste mitglied",

        "quem e o melhor do servidor",
        "quem e o melhor no servidor",
        "quem e o melhor membro",

        "chi e il migliore del server",
        "chi e il migliore sul server",

        "quien es el millor del servidor",
        "qui es el millor del servidor"
    ]

    if any(phrase in text for phrase in best_phrases):
        return "best"

    # -----------------------------------------------------
    # SERVER CREATOR
    # -----------------------------------------------------

    server_creator_phrases = [
        "who created the server",
        "who made the server",
        "who owns the server",
        "who is the server owner",
        "who is the owner of the server",
        "who founded the server",
        "who is the founder of the server",
        "who is the server founder",
        "who built the server",
        "server creator",

        "quien creo el servidor",
        "quien hizo el servidor",
        "quien creo este servidor",
        "quien hizo este servidor",
        "quien es el dueno del servidor",
        "quien es el propietario del servidor",
        "quien es el fundador del servidor",

        "qui a cree le serveur",
        "qui a fait le serveur",
        "qui est le proprietaire du serveur",
        "qui est le fondateur du serveur",

        "wer hat den server erstellt",
        "wer hat den server gemacht",
        "wer ist der serverbesitzer",
        "wer ist der grunder des servers",

        "quem criou o servidor",
        "quem fez o servidor",
        "quem e o dono do servidor",
        "quem e o fundador do servidor",

        "chi ha creato il server",
        "chi ha fatto il server",
        "chi e il proprietario del server",

        "qui ha creat el servidor",
        "qui ha fet el servidor",
        "qui es el propietari del servidor",
        "qui es el fundador del servidor"
    ]

    if any(
        phrase in text
        for phrase in server_creator_phrases
    ):
        return "server_creator"

    # -----------------------------------------------------
    # AI CREATOR
    # -----------------------------------------------------

    ai_creator_phrases = [
        "who is your creator",
        "who created you",
        "who made you",
        "who built you",
        "who created abelai",
        "who made abelai",
        "creator of abelai",
        "creator of this ai",
        "who is your developer",

        "quien es el creador de la ia",
        "quien creo la ia",
        "quien hizo la ia",
        "quien te creo",
        "quien te hizo",
        "quien creo abelai",
        "quien hizo abelai",
        "creador de abelai",
        "creador de la ia",

        "qui t'a cree",
        "qui a cree abelai",
        "qui a cree cette ia",

        "wer hat dich erstellt",
        "wer hat dich gemacht",
        "wer hat abelai erstellt",

        "quem te criou",
        "quem fez voce",
        "quem criou abelai",

        "chi ti ha creato",
        "chi ha creato abelai",

        "qui t'ha creat",
        "qui ha creat abelai"
    ]

    if any(
        phrase in text
        for phrase in ai_creator_phrases
    ):
        return "ai_creator"

    return None


# =========================================================
# DISCORD CLIENT
# =========================================================

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = discord.Client(intents=intents)


# =========================================================
# BOT READY
# =========================================================

@bot.event
async def on_ready():
    print()
    print("Starting AbelAI...")
    print("Individual memory system loaded.")
    print("Anti-mention system loaded.")
    print("Moderation system loaded.")
    print("Timeout configured: 1 hour.")
    print("Default language: English.")
    print("Automatic language switching enabled.")
    print(f"Groq model: {GROQ_MODEL}")
    print()
    print(f"Connected as: {bot.user}")
    print(f"Bot ID: {bot.user.id}")
    print()


# =========================================================
# MESSAGE HANDLER
# =========================================================

@bot.event
async def on_message(message):

    if message.author.bot:
        return

    # -----------------------------------------------------
    # MODERATION
    # -----------------------------------------------------

    if detect_insult(message.content):
        print(
            f"Insult detected from {message.author}: "
            f"{message.content}"
        )

        if isinstance(message.author, discord.Member):
            member = message.author
            guild = message.guild

            if guild and guild.owner_id == member.id:
                print("Server owner is exempt from timeout.")

            else:
                try:
                    bot_member = guild.me if guild else None

                    if (
                        guild
                        and bot_member
                        and member.top_role >= bot_member.top_role
                    ):
                        print(
                            "Cannot timeout member because "
                            "of role hierarchy."
                        )

                    else:
                        await member.timeout(
                            timedelta(hours=1),
                            reason="Insult detected by AbelAI"
                        )

                        await message.channel.send(
                            "You have received a 1-hour timeout "
                            "for insulting.",
                            allowed_mentions=discord.AllowedMentions.none()
                        )

                        return

                except discord.Forbidden:
                    print(
                        "Missing permission to timeout this member."
                    )

                except discord.HTTPException as error:
                    print(f"Discord moderation error: {error}")

    # -----------------------------------------------------
    # CLEAR PERSONAL MEMORY
    # -----------------------------------------------------

    if message.content.lower().strip() == "?clear":
        clear_memory(message.author.id)

        # Match the language of the command user's message.
        await message.channel.send(
            "Your personal memory has been cleared.",
            allowed_mentions=discord.AllowedMentions.none()
        )
        return

    # -----------------------------------------------------
    # SPECIAL QUESTIONS
    # -----------------------------------------------------

    special_type = get_special_answer_type(message.content)

    if special_type == "best":
        await message.channel.send(
            "Abel997899.",
            allowed_mentions=discord.AllowedMentions.none()
        )
        return

    if special_type == "server_creator":
        await message.channel.send(
            "Abel997899.",
            allowed_mentions=discord.AllowedMentions.none()
        )
        return

    if special_type == "ai_creator":
        text = normalize_text(message.content)

        spanish_words = [
            "quien", "creador", "creo", "hizo", "te"
        ]

        if any(word in text.split() for word in spanish_words):
            answer = f"El creador de esta IA es {CREADOR}."
        else:
            answer = f"The creator of this AI is {CREADOR}."

        await message.channel.send(
            answer,
            allowed_mentions=discord.AllowedMentions.none()
        )
        return

    # -----------------------------------------------------
    # ?AI COMMAND
    # -----------------------------------------------------

    if not message.content.lower().startswith("?ai"):
        return

    pregunta = message.content[3:].strip()

    if not pregunta:
        await message.channel.send(
            "Please write a question after `?ai`.",
            allowed_mentions=discord.AllowedMentions.none()
        )
        return

    # -----------------------------------------------------
    # SAVE USER NAME
    # -----------------------------------------------------

    nombre = detect_name(pregunta)

    if nombre:
        save_fact(
            message.author.id,
            "nombre",
            nombre
        )

        print(
            f"Saved user name: {message.author} -> {nombre}"
        )

    # -----------------------------------------------------
    # LOAD INDIVIDUAL MEMORY
    # -----------------------------------------------------

    memoria = get_memory(message.author.id)
    hechos = get_facts(message.author.id)

    contexto_memoria = [
        {"role": role, "content": content}
        for role, content in memoria
    ]

    datos_usuario = ""

    for fact_type, fact_value in hechos:
        if fact_type == "nombre":
            datos_usuario += (
                f"\nThe user's name is {fact_value}."
            )

    # Save the current question after loading previous memory.
    save_message(
        message.author.id,
        "user",
        pregunta
    )

    # -----------------------------------------------------
    # SYSTEM PROMPT
    # -----------------------------------------------------

    system_prompt = f"""
You are AbelAI, an AI assistant running on Discord.

Your creator is {CREADOR}.

LANGUAGE RULES — VERY IMPORTANT:

- English is your default and preferred language.
- If the user's current message is clearly written in another
  language, respond in that same language.
- If the user writes in English, respond in English.
- If the user writes in Spanish, respond in Spanish.
- If the user writes in French, respond in French.
- If the user writes in German, respond in German.
- If the user writes in Catalan, respond in Catalan.
- If the user writes in Portuguese, respond in Portuguese.
- Apply the same rule to every other language.
- If the user switches languages, switch immediately.
- Previous conversation history must not override the language
  of the current message.
- If the language is unclear, use English.

IMPORTANT SERVER FACTS:

- If asked who is the best on the server, the answer is Abel997899.
- If asked who created the server, the answer is Abel997899.
- If asked who created AbelAI, the answer is {CREADOR}.
- Do not change these answers.

BEHAVIOUR:

- Be helpful, friendly, natural, and respectful.
- Keep answers concise unless more detail is needed.
- Use emojis when appropriate.
- If you do not know something, say so clearly.
- Never generate Discord mentions.
- Never use the @ symbol.
- Never generate user, role, everyone, or here mentions.
- Never mix information between different users.
- Only use the memory belonging to the current user.

USER INFORMATION:
{datos_usuario}
"""

    messages = [
        {
            "role": "system",
            "content": system_prompt
        }
    ]

    messages.extend(contexto_memoria)

    messages.append({
        "role": "user",
        "content": pregunta
    })

    # -----------------------------------------------------
    # CALL GROQ
    # -----------------------------------------------------

    try:
        async with message.channel.typing():
            respuesta = await asyncio.to_thread(
                ai.chat.completions.create,
                model=GROQ_MODEL,
                messages=messages,
                temperature=0.7,
                max_tokens=1000
            )

        texto = respuesta.choices[0].message.content

        if not texto:
            texto = "I couldn't generate a response. Please try again."

        texto = remove_mentions(texto)

        save_message(
            message.author.id,
            "assistant",
            texto
        )

        # Discord message limit: 2,000 characters.
        partes = [
            texto[i:i + 1900]
            for i in range(0, len(texto), 1900)
        ]

        for parte in partes:
            await message.channel.send(
                parte,
                allowed_mentions=discord.AllowedMentions.none()
            )

    except Exception as error:
        print(f"Groq error: {error}")

        await message.channel.send(
            "An error occurred while talking to the AI. Please try again.",
            allowed_mentions=discord.AllowedMentions.none()
        )


# =========================================================
# START BOT
# =========================================================

print("AbelAI is starting...")

bot.run(DISCORD_TOKEN)
