import os
import re
import json
import asyncio
from pathlib import Path
from datetime import timedelta
from collections import defaultdict, deque

import discord
from discord import app_commands


# =========================================================
# TOKEN
# =========================================================

TOKEN = os.getenv("DISCORD_BOT_TOKEN")


# =========================================================
# SERVER NAMES
# =========================================================

VERIFIED_ROLE_NAME = "Verified"

CATEGORY_NAME = "✅ VERIFICATION"

RULES_CHANNEL_NAME = "📜・rules"
VERIFY_CHANNEL_NAME = "✅・verification"
WELCOME_CHANNEL_NAME = "👋・welcome"
GENERAL_CHANNEL_NAME = "💬・general"

MOD_LOG_CHANNEL_NAME = "🛡️・mod-logs"
MOD_REVIEW_CHANNEL_NAME = "🔎・mod-review"

SHARED_MODS_NAME = "🧩・shared-mods"
SUGGESTIONS_NAME = "💡・suggestions"


# =========================================================
# COOLDOWNS
# =========================================================

GENERAL_SLOWMODE_SECONDS = 10

SHARED_MOD_COMMENT_SLOWMODE = 10

SUGGESTION_POST_COOLDOWN = 300
SUGGESTION_COMMENT_SLOWMODE = 10

MOD_SUBMIT_COOLDOWN_SECONDS = 600


# =========================================================
# MODERATION SETTINGS
# =========================================================

BAD_WORD_TIMEOUT_MINUTES = 30

SPAM_TIMEOUT_MINUTES = 10
SPAM_MESSAGE_LIMIT = 6
SPAM_WINDOW_SECONDS = 8

MASS_MENTION_LIMIT = 5
MASS_MENTION_TIMEOUT_MINUTES = 30


# =========================================================
# RAID PROTECTION
# =========================================================

RAID_JOIN_LIMIT = 6
RAID_JOIN_WINDOW_SECONDS = 10

MIN_ACCOUNT_AGE_HOURS = 24


# =========================================================
# ALLOWED MOD FILE TYPES
# =========================================================

ALLOWED_MOD_EXTENSIONS = {
    ".zip",
    ".rar",
    ".7z",
    ".dll",
    ".py",
    ".js",
    ".txt",
}


# =========================================================
# FILE STORAGE
# =========================================================
#
# If Railway has /data mounted as a Volume,
# warnings + mod cooldowns can survive redeploys.
#

if Path("/data").exists():

    DATA_FOLDER = Path("/data")

else:

    DATA_FOLDER = Path(".")


WARNINGS_FILE = DATA_FOLDER / "warnings.json"

MOD_COOLDOWNS_FILE = DATA_FOLDER / "mod_cooldowns.json"


# =========================================================
# INTENTS
# =========================================================
#
# Discord Developer Portal -> Bot:
#
# SERVER MEMBERS INTENT     = ON
# MESSAGE CONTENT INTENT    = ON
# PRESENCE INTENT           = OFF
#

intents = discord.Intents.default()

intents.members = True
intents.message_content = True


client = discord.Client(
    intents=intents
)

tree = app_commands.CommandTree(
    client
)


# =========================================================
# MEMORY
# =========================================================

message_times = defaultdict(
    deque
)

recent_joins = defaultdict(
    deque
)

raid_lockdowns = set()

views_registered = False


# =========================================================
# BAD LANGUAGE
# =========================================================

BAD_PHRASES = [
    "fuck",
    "kill yourself",
    "go kill yourself",
    "kys",
    "go kys",
    "retard",
]


NWORD_PATTERN = re.compile(
    r"\bn[\W_]*[i1!][\W_]*g[\W_]*g[\W_]*"
    r"[e3a@][\W_]*r?s?\b",
    re.IGNORECASE
)


INVITE_PATTERN = re.compile(
    r"(?:https?://)?"
    r"(?:www\.)?"
    r"(?:discord\.gg|discord(?:app)?\.com/invite)"
    r"/[A-Za-z0-9-]+",
    re.IGNORECASE
)


GIF_PATTERN = re.compile(
    r"(?:https?://\S+\.gif(?:\?\S*)?$)|"
    r"(?:https?://)?"
    r"(?:www\.)?"
    r"(?:tenor\.com|giphy\.com|media\.giphy\.com)"
    r"/\S+",
    re.IGNORECASE
)


URL_PATTERN = re.compile(
    r"https?://\S+",
    re.IGNORECASE
)


# =========================================================
# JSON HELPERS
# =========================================================

def load_json(path):

    if not path.exists():
        return {}

    try:

        with open(
            path,
            "r",
            encoding="utf-8"
        ) as file:

            return json.load(file)

    except Exception:

        return {}


def save_json(
    path,
    data
):

    try:

        path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        with open(
            path,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                data,
                file,
                indent=2
            )

    except Exception as error:

        print(
            "JSON SAVE ERROR:",
            repr(error)
        )


warnings_data = load_json(
    WARNINGS_FILE
)

mod_cooldowns = load_json(
    MOD_COOLDOWNS_FILE
)


# =========================================================
# WARNING FUNCTIONS
# =========================================================

def warning_key(
    guild_id,
    user_id
):

    return f"{guild_id}:{user_id}"


def get_user_warnings(
    guild_id,
    user_id
):

    key = warning_key(
        guild_id,
        user_id
    )

    return warnings_data.get(
        key,
        []
    )


def add_user_warning(
    guild_id,
    user_id,
    moderator_id,
    reason
):

    key = warning_key(
        guild_id,
        user_id
    )

    warnings_data.setdefault(
        key,
        []
    )

    warnings_data[key].append({
        "moderator": moderator_id,
        "reason": reason,
        "time": discord.utils.utcnow().isoformat()
    })

    save_json(
        WARNINGS_FILE,
        warnings_data
    )


def clear_user_warnings(
    guild_id,
    user_id
):

    key = warning_key(
        guild_id,
        user_id
    )

    warnings_data.pop(
        key,
        None
    )

    save_json(
        WARNINGS_FILE,
        warnings_data
    )


# =========================================================
# MOD COOLDOWN FUNCTIONS
# =========================================================

def mod_cooldown_key(
    guild_id,
    user_id
):

    return f"{guild_id}:{user_id}"


def get_mod_cooldown(
    guild_id,
    user_id
):

    key = mod_cooldown_key(
        guild_id,
        user_id
    )

    value = mod_cooldowns.get(
        key
    )

    if not value:
        return None

    try:

        return discord.utils.parse_time(
            value
        )

    except Exception:

        return None


def set_mod_cooldown(
    guild_id,
    user_id
):

    key = mod_cooldown_key(
        guild_id,
        user_id
    )

    mod_cooldowns[key] = (
        discord.utils.utcnow().isoformat()
    )

    save_json(
        MOD_COOLDOWNS_FILE,
        mod_cooldowns
    )


# =========================================================
# HELPERS
# =========================================================

def is_staff(
    member
):

    if not isinstance(
        member,
        discord.Member
    ):

        return False

    permissions = member.guild_permissions

    return (
        permissions.administrator
        or permissions.manage_guild
        or permissions.manage_messages
        or permissions.moderate_members
    )


def allowed_mod_file(
    filename
):

    extension = Path(
        filename.lower()
    ).suffix

    return extension in ALLOWED_MOD_EXTENSIONS


def contains_bad_language(
    text
):

    if NWORD_PATTERN.search(
        text
    ):

        return True

    lowered = text.lower()

    return any(
        phrase in lowered
        for phrase in BAD_PHRASES
    )


async def safe_delete(
    message
):

    try:

        await message.delete()

    except (
        discord.Forbidden,
        discord.NotFound
    ):

        pass


async def temporary_warning(
    channel,
    member,
    text
):

    try:

        warning = await channel.send(
            f"{member.mention} {text}"
        )

        await asyncio.sleep(
            7
        )

        await warning.delete()

    except Exception:

        pass


async def timeout_member(
    member,
    minutes,
    reason
):

    try:

        await member.timeout(
            timedelta(
                minutes=minutes
            ),
            reason=reason
        )

        return True

    except (
        discord.Forbidden,
        discord.HTTPException
    ):

        return False


async def mod_log(
    guild,
    title,
    description,
    color=discord.Color.orange()
):

    channel = discord.utils.get(
        guild.text_channels,
        name=MOD_LOG_CHANNEL_NAME
    )

    if channel is None:
        return

    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=discord.utils.utcnow()
    )

    try:

        await channel.send(
            embed=embed
        )

    except Exception:

        pass


# =========================================================
# FAST SPAM
# =========================================================

async def check_fast_spam(
    message,
    scope
):

    guild = message.guild
    member = message.author

    key = (
        guild.id,
        member.id,
        scope
    )

    now = discord.utils.utcnow()

    times = message_times[key]

    times.append(
        now
    )

    cutoff = now - timedelta(
        seconds=SPAM_WINDOW_SECONDS
    )

    while (
        times
        and times[0] < cutoff
    ):

        times.popleft()


    if len(times) >= SPAM_MESSAGE_LIMIT:

        times.clear()

        await safe_delete(
            message
        )

        success = await timeout_member(
            member,
            SPAM_TIMEOUT_MINUTES,
            "Fast message spam"
        )

        if success:

            await temporary_warning(
                message.channel,
                member,
                (
                    "⚠️ Spam detected. "
                    "You have been timed out for "
                    f"**{SPAM_TIMEOUT_MINUTES} minutes**."
                )
            )

        await mod_log(
            guild,
            "⚠️ Spam timeout",
            (
                f"User: {member.mention}\n"
                f"Reason: {SPAM_MESSAGE_LIMIT}+ messages "
                f"in {SPAM_WINDOW_SECONDS} seconds\n"
                f"Timeout: {SPAM_TIMEOUT_MINUTES} minutes"
            )
        )

        return True


    return False


# =========================================================
# VERIFY BUTTON
# =========================================================

class VerifyView(
    discord.ui.View
):

    def __init__(
        self
    ):

        super().__init__(
            timeout=None
        )


    @discord.ui.button(
        label="Verify",
        emoji="✅",
        style=discord.ButtonStyle.green,
        custom_id="ssp_verify_button_v10"
    )
    async def verify_button(
        self,
        interaction,
        button
    ):

        guild = interaction.guild

        if guild is None:

            await interaction.response.send_message(
                "❌ Verification only works inside the server.",
                ephemeral=True
            )

            return


        member = interaction.user

        if not isinstance(
            member,
            discord.Member
        ):

            return


        role = discord.utils.get(
            guild.roles,
            name=VERIFIED_ROLE_NAME
        )


        if role is None:

            await interaction.response.send_message(
                "❌ Verified role is missing.",
                ephemeral=True
            )

            return


        if role in member.roles:

            await interaction.response.send_message(
                "✅ You are already verified.",
                ephemeral=True
            )

            return


        # =================================================
        # ACCOUNT AGE CHECK
        # =================================================

        account_age = (
            discord.utils.utcnow()
            - member.created_at
        )


        if account_age < timedelta(
            hours=MIN_ACCOUNT_AGE_HOURS
        ):

            await interaction.response.send_message(
                (
                    "🛡️ Your Discord account is too new "
                    "to verify automatically.\n\n"
                    f"Accounts must be at least "
                    f"**{MIN_ACCOUNT_AGE_HOURS} hours old**."
                ),
                ephemeral=True
            )

            await mod_log(
                guild,
                "🛡️ New account blocked",
                (
                    f"User: {member.mention}\n"
                    f"Account age: {account_age}"
                )
            )

            return


        # =================================================
        # RAID LOCKDOWN
        # =================================================

        if guild.id in raid_lockdowns:

            await interaction.response.send_message(
                (
                    "🚨 Verification is temporarily locked "
                    "because raid protection is active."
                ),
                ephemeral=True
            )

            return


        bot_member = guild.me


        if (
            bot_member is None
            or role >= bot_member.top_role
        ):

            await interaction.response.send_message(
                (
                    "❌ My bot role must be above "
                    "the Verified role."
                ),
                ephemeral=True
            )

            return


        try:

            await member.add_roles(
                role,
                reason="SSP verification"
            )


            # =============================================
            # WELCOME CHANNEL
            # =============================================

            welcome_channel = discord.utils.get(
                guild.text_channels,
                name=WELCOME_CHANNEL_NAME
            )


            if welcome_channel:

                embed = discord.Embed(
                    title="👋 Welcome!",
                    description=(
                        f"Welcome {member.mention} to "
                        f"**{guild.name}**!\n\n"
                        "You are now verified and have access "
                        "to General, Shared Mods, and Suggestions."
                    ),
                    color=discord.Color.green()
                )

                try:

                    await welcome_channel.send(
                        embed=embed
                    )

                except Exception:

                    pass


            # =============================================
            # VERIFICATION LOG
            # =============================================

            await mod_log(
                guild,
                "✅ Member Verified",
                (
                    f"User: {member.mention}\n"
                    f"User ID: `{member.id}`\n"
                    f"Account created: "
                    f"<t:{int(member.created_at.timestamp())}:R>"
                ),
                discord.Color.green()
            )


            await interaction.response.send_message(
                (
                    "✅ **You are verified!**\n\n"
                    "You now have access to:\n"
                    "💬 General\n"
                    "🧩 Shared Mods\n"
                    "💡 Suggestions"
                ),
                ephemeral=True
            )


        except discord.Forbidden:

            await interaction.response.send_message(
                (
                    "❌ I couldn't give you the Verified role.\n"
                    "Make sure I have **Manage Roles**."
                ),
                ephemeral=True
            )


# =========================================================
# READY
# =========================================================

@client.event
async def on_ready():

    global views_registered


    if not views_registered:

        client.add_view(
            VerifyView()
        )

        views_registered = True


    print("")
    print("======================================")
    print("✅ SSP MODDING HUB BOT ONLINE")
    print("======================================")
    print(
        "Bot:",
        client.user
    )
    print(
        "Servers:",
        len(client.guilds)
    )


    try:

        synced = await tree.sync()

        print(
            "Slash commands:",
            len(synced)
        )

    except Exception as error:

        print(
            "SYNC ERROR:",
            repr(error)
        )


    print("======================================")
    print("")


# =========================================================
# MESSAGE MODERATION
# =========================================================

@client.event
async def on_message(
    message
):

    if message.guild is None:
        return


    if message.author.bot:
        return


    if not isinstance(
        message.author,
        discord.Member
    ):

        return


    guild = message.guild
    member = message.author


    if is_staff(
        member
    ):

        return


    rules = discord.utils.get(
        guild.text_channels,
        name=RULES_CHANNEL_NAME
    )

    verify = discord.utils.get(
        guild.text_channels,
        name=VERIFY_CHANNEL_NAME
    )

    general = discord.utils.get(
        guild.text_channels,
        name=GENERAL_CHANNEL_NAME
    )


    # =====================================================
    # RULES + VERIFY = READ ONLY
    # =====================================================

    if message.channel in (
        rules,
        verify
    ):

        await safe_delete(
            message
        )

        return


    # =====================================================
    # FORUM THREAD MODERATION
    # =====================================================

    if isinstance(
        message.channel,
        discord.Thread
    ):

        parent = message.channel.parent


        if isinstance(
            parent,
            discord.ForumChannel
        ):

            if parent.name in (
                SHARED_MODS_NAME,
                SUGGESTIONS_NAME
            ):

                # =========================================
                # BAD LANGUAGE
                # =========================================

                if contains_bad_language(
                    message.content or ""
                ):

                    await safe_delete(
                        message
                    )

                    await timeout_member(
                        member,
                        BAD_WORD_TIMEOUT_MINUTES,
                        "Prohibited language"
                    )

                    await mod_log(
                        guild,
                        "🚫 Forum timeout",
                        (
                            f"User: {member.mention}\n"
                            f"Forum: {parent.name}\n"
                            f"Timeout: "
                            f"{BAD_WORD_TIMEOUT_MINUTES} minutes"
                        )
                    )

                    return


                # =========================================
                # MASS PINGS
                # =========================================

                mention_count = (
                    len(message.mentions)
                    + len(message.role_mentions)
                )


                if (
                    message.mention_everyone
                    or mention_count >= MASS_MENTION_LIMIT
                ):

                    await safe_delete(
                        message
                    )

                    await timeout_member(
                        member,
                        MASS_MENTION_TIMEOUT_MINUTES,
                        "Mass mention spam"
                    )

                    await mod_log(
                        guild,
                        "🚨 Mass ping timeout",
                        (
                            f"User: {member.mention}\n"
                            f"Forum: {parent.name}"
                        )
                    )

                    return


                await check_fast_spam(
                    message,
                    f"forum_{parent.id}"
                )

                return


    # =====================================================
    # GENERAL
    # =====================================================

    if (
        general is None
        or message.channel.id != general.id
    ):

        return


    text = message.content or ""


    # =====================================================
    # FILES / IMAGES
    # =====================================================

    if message.attachments:

        await safe_delete(
            message
        )

        await temporary_warning(
            message.channel,
            member,
            (
                "⚠️ General is **text only**. "
                "Files and images are not allowed."
            )
        )

        return


    # =====================================================
    # STICKERS
    # =====================================================

    if message.stickers:

        await safe_delete(
            message
        )

        await temporary_warning(
            message.channel,
            member,
            "⚠️ Stickers are not allowed."
        )

        return


    # =====================================================
    # GIFS
    # =====================================================

    if GIF_PATTERN.search(
        text
    ):

        await safe_delete(
            message
        )

        await temporary_warning(
            message.channel,
            member,
            "⚠️ GIFs are not allowed."
        )

        return


    # =====================================================
    # DISCORD INVITES
    # =====================================================

    if INVITE_PATTERN.search(
        text
    ):

        await safe_delete(
            message
        )

        await temporary_warning(
            message.channel,
            member,
            "⚠️ Discord invites are not allowed."
        )

        return


    # =====================================================
    # OTHER LINKS
    # =====================================================

    if URL_PATTERN.search(
        text
    ):

        await safe_delete(
            message
        )

        await temporary_warning(
            message.channel,
            member,
            "⚠️ Links are not allowed in General."
        )

        return


    # =====================================================
    # MASS MENTION
    # =====================================================

    mention_count = (
        len(message.mentions)
        + len(message.role_mentions)
    )


    if (
        message.mention_everyone
        or mention_count >= MASS_MENTION_LIMIT
    ):

        await safe_delete(
            message
        )

        success = await timeout_member(
            member,
            MASS_MENTION_TIMEOUT_MINUTES,
            "Mass mention spam"
        )

        if success:

            await temporary_warning(
                message.channel,
                member,
                (
                    "🚫 Mass ping detected. "
                    "You have been timed out for "
                    f"**{MASS_MENTION_TIMEOUT_MINUTES} minutes**."
                )
            )


        await mod_log(
            guild,
            "🚨 Mass mention timeout",
            (
                f"User: {member.mention}\n"
                f"Mentions: {mention_count}\n"
                f"Timeout: "
                f"{MASS_MENTION_TIMEOUT_MINUTES} minutes"
            )
        )

        return


    # =====================================================
    # BAD LANGUAGE
    # =====================================================

    if contains_bad_language(
        text
    ):

        await safe_delete(
            message
        )

        success = await timeout_member(
            member,
            BAD_WORD_TIMEOUT_MINUTES,
            "Prohibited language / harassment"
        )

        if success:

            await temporary_warning(
                message.channel,
                member,
                (
                    "🚫 That language is not allowed. "
                    "You have been timed out for "
                    f"**{BAD_WORD_TIMEOUT_MINUTES} minutes**."
                )
            )


        await mod_log(
            guild,
            "🚫 Language timeout",
            (
                f"User: {member.mention}\n"
                f"Timeout: {BAD_WORD_TIMEOUT_MINUTES} minutes"
            )
        )

        return


    # =====================================================
    # FAST SPAM
    # =====================================================

    await check_fast_spam(
        message,
        "general"
    )


# =========================================================
# RAID DETECTION
# =========================================================

@client.event
async def on_member_join(
    member
):

    guild = member.guild

    now = discord.utils.utcnow()

    joins = recent_joins[
        guild.id
    ]

    joins.append(
        now
    )

    cutoff = now - timedelta(
        seconds=RAID_JOIN_WINDOW_SECONDS
    )

    while (
        joins
        and joins[0] < cutoff
    ):

        joins.popleft()


    if len(joins) < RAID_JOIN_LIMIT:
        return


    if guild.id in raid_lockdowns:
        return


    raid_lockdowns.add(
        guild.id
    )


    verified_role = discord.utils.get(
        guild.roles,
        name=VERIFIED_ROLE_NAME
    )


    general = discord.utils.get(
        guild.text_channels,
        name=GENERAL_CHANNEL_NAME
    )


    if (
        verified_role
        and general
    ):

        try:

            overwrite = general.overwrites_for(
                verified_role
            )

            overwrite.send_messages = False


            await general.set_permissions(
                verified_role,
                overwrite=overwrite,
                reason="Automatic raid lockdown"
            )

        except discord.Forbidden:

            pass


    await mod_log(
        guild,
        "🚨 RAID LOCKDOWN ACTIVATED",
        (
            f"{RAID_JOIN_LIMIT}+ accounts joined "
            f"in {RAID_JOIN_WINDOW_SECONDS} seconds.\n\n"
            "Verification is disabled and General is locked.\n"
            "Use `/unlock` after checking the server."
        ),
        discord.Color.red()
    )


# =========================================================
# /PING
# =========================================================

@tree.command(
    name="ping",
    description="Check if the bot is online"
)
async def ping(
    interaction
):

    latency = round(
        client.latency * 1000
    )

    await interaction.response.send_message(
        f"🏓 Pong! `{latency}ms`",
        ephemeral=True
    )


# =========================================================
# /SETUP
# =========================================================

@tree.command(
    name="setup",
    description="Create or update the SSP server system"
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def setup(
    interaction
):

    guild = interaction.guild

    if guild is None:

        await interaction.response.send_message(
            "❌ Use this command inside your server.",
            ephemeral=True
        )

        return


    await interaction.response.defer(
        ephemeral=True
    )


    everyone = guild.default_role

    bot_member = guild.me


    # =====================================================
    # VERIFIED ROLE
    # =====================================================

    verified = discord.utils.get(
        guild.roles,
        name=VERIFIED_ROLE_NAME
    )


    if verified is None:

        verified = await guild.create_role(
            name=VERIFIED_ROLE_NAME,
            reason="SSP verification"
        )


    # =====================================================
    # CATEGORY
    # =====================================================

    category = discord.utils.get(
        guild.categories,
        name=CATEGORY_NAME
    )


    if category is None:

        category = await guild.create_category(
            CATEGORY_NAME,
            reason="SSP setup"
        )


    # =====================================================
    # RULES
    # =====================================================

    rules = discord.utils.get(
        guild.text_channels,
        name=RULES_CHANNEL_NAME
    )


    if rules is None:

        rules = await guild.create_text_channel(
            RULES_CHANNEL_NAME,
            category=category
        )


    # =====================================================
    # VERIFY
    # =====================================================

    verify = discord.utils.get(
        guild.text_channels,
        name=VERIFY_CHANNEL_NAME
    )


    if verify is None:

        verify = await guild.create_text_channel(
            VERIFY_CHANNEL_NAME,
            category=category
        )


    # =====================================================
    # WELCOME
    # =====================================================

    welcome = discord.utils.get(
        guild.text_channels,
        name=WELCOME_CHANNEL_NAME
    )


    if welcome is None:

        welcome = await guild.create_text_channel(
            WELCOME_CHANNEL_NAME,
            category=category
        )


    # =====================================================
    # GENERAL
    # =====================================================

    general = discord.utils.get(
        guild.text_channels,
        name=GENERAL_CHANNEL_NAME
    )


    if general is None:

        general = await guild.create_text_channel(
            GENERAL_CHANNEL_NAME,
            category=category,
            slowmode_delay=GENERAL_SLOWMODE_SECONDS
        )


    # =====================================================
    # MOD LOGS
    # =====================================================

    mod_logs = discord.utils.get(
        guild.text_channels,
        name=MOD_LOG_CHANNEL_NAME
    )


    if mod_logs is None:

        mod_logs = await guild.create_text_channel(
            MOD_LOG_CHANNEL_NAME,
            category=category
        )


    # =====================================================
    # MOD REVIEW
    # =====================================================

    mod_review = discord.utils.get(
        guild.text_channels,
        name=MOD_REVIEW_CHANNEL_NAME
    )


    if mod_review is None:

        mod_review = await guild.create_text_channel(
            MOD_REVIEW_CHANNEL_NAME,
            category=category
        )


    # =====================================================
    # SHARED MODS FORUM
    # =====================================================

    shared_mods = discord.utils.get(
        guild.forums,
        name=SHARED_MODS_NAME
    )


    if shared_mods is None:

        shared_mods = await guild.create_forum(
            name=SHARED_MODS_NAME,

            category=category,

            topic=(
                "⚠️ Community-uploaded mods. "
                "Do not automatically trust every file."
            ),

            default_thread_slowmode_delay=(
                SHARED_MOD_COMMENT_SLOWMODE
            )
        )


    # =====================================================
    # SUGGESTIONS FORUM
    # =====================================================

    suggestions = discord.utils.get(
        guild.forums,
        name=SUGGESTIONS_NAME
    )


    if suggestions is None:

        suggestions = await guild.create_forum(
            name=SUGGESTIONS_NAME,

            category=category,

            topic=(
                "💡 Suggest ideas for SSP Modding Hub."
            ),

            slowmode_delay=(
                SUGGESTION_POST_COOLDOWN
            ),

            default_thread_slowmode_delay=(
                SUGGESTION_COMMENT_SLOWMODE
            )
        )


    # =====================================================
    # RULES PERMISSIONS
    # =====================================================

    await rules.set_permissions(
        everyone,

        view_channel=True,
        send_messages=False,
        add_reactions=False,

        create_public_threads=False,
        create_private_threads=False,
        send_messages_in_threads=False
    )


    # =====================================================
    # VERIFY PERMISSIONS
    # =====================================================

    await verify.set_permissions(
        everyone,

        view_channel=True,
        send_messages=False,
        add_reactions=False,

        create_public_threads=False,
        create_private_threads=False,
        send_messages_in_threads=False
    )


    # =====================================================
    # WELCOME
    # =====================================================

    await welcome.set_permissions(
        everyone,
        view_channel=True,
        send_messages=False,
        add_reactions=False
    )


    # =====================================================
    # GENERAL
    # =====================================================

    await general.set_permissions(
        everyone,
        view_channel=False,
        send_messages=False
    )


    await general.set_permissions(
        verified,

        view_channel=True,
        send_messages=True,

        attach_files=False,
        embed_links=False,

        add_reactions=False,

        create_public_threads=False,
        create_private_threads=False,
        send_messages_in_threads=False,

        read_message_history=True
    )


    await general.edit(
        slowmode_delay=GENERAL_SLOWMODE_SECONDS
    )


    # =====================================================
    # SHARED MODS
    # =====================================================
    #
    # Users DO NOT create posts directly.
    # Approved submissions are published by the bot.
    #

    await shared_mods.set_permissions(
        everyone,

        view_channel=False,
        create_public_threads=False,
        send_messages=False
    )


    await shared_mods.set_permissions(
        verified,

        view_channel=True,

        create_public_threads=False,

        send_messages=True,
        send_messages_in_threads=True,

        attach_files=False,

        read_message_history=True
    )


    # =====================================================
    # SUGGESTIONS
    # =====================================================

    await suggestions.set_permissions(
        everyone,
        view_channel=False
    )


    await suggestions.set_permissions(
        verified,

        view_channel=True,

        create_public_threads=True,

        send_messages=True,
        send_messages_in_threads=True,

        attach_files=False,

        read_message_history=True
    )


    # =====================================================
    # MOD LOGS + MOD REVIEW PRIVATE
    # =====================================================

    await mod_logs.set_permissions(
        everyone,
        view_channel=False
    )


    await verified.set_permissions if False else asyncio.sleep(0)


    await mod_review.set_permissions(
        everyone,
        view_channel=False
    )


    # =====================================================
    # INITIAL POSTS
    # =====================================================

    if not [
        message
        async for message in rules.history(
            limit=1
        )
    ]:

        rules_embed = discord.Embed(
            title="📜 SSP Modding Hub Rules",
            description=(
                "• No spam\n"
                "• No mass pings\n"
                "• No links, GIFs, files, or Discord invites in General\n"
                "• No harassment or slurs\n"
                "• Be respectful\n"
                "• Follow Discord's rules\n\n"
                "💬 General has a **10-second cooldown**.\n\n"
                "🧩 Mods must be submitted with `/submitmod` "
                "and approved by staff before appearing in Shared Mods."
            ),
            color=discord.Color.blue()
        )


        await rules.send(
            embed=rules_embed
        )


    if not [
        message
        async for message in verify.history(
            limit=1
        )
    ]:

        verify_embed = discord.Embed(
            title="✅ Verification",
            description=(
                "Press **✅ Verify** below.\n\n"
                "After verification you unlock:\n"
                "💬 General\n"
                "🧩 Shared Mods\n"
                "💡 Suggestions"
            ),
            color=discord.Color.green()
        )


        await verify.send(
            embed=verify_embed,
            view=VerifyView()
        )


    await interaction.followup.send(
        (
            "✅ **Setup/update complete!**\n\n"
            "Added/updated:\n"
            "📜 Rules\n"
            "✅ Verification\n"
            "👋 Welcome\n"
            "💬 General\n"
            "🧩 Shared Mods\n"
            "💡 Suggestions\n"
            "🛡️ Mod Logs\n"
            "🔎 Mod Review"
        ),
        ephemeral=True
    )


# =========================================================
# /SUBMITMOD
# =========================================================

@tree.command(
    name="submitmod",
    description="Submit a mod for staff approval"
)
@app_commands.describe(
    name="Name of the mod",
    file="Upload exactly one mod file",
    description="Short description of the mod"
)
async def submitmod(
    interaction,
    name: str,
    file: discord.Attachment,
    description: str = "No description provided"
):

    guild = interaction.guild

    if guild is None:
        return


    member = interaction.user


    if not isinstance(
        member,
        discord.Member
    ):

        return


    verified = discord.utils.get(
        guild.roles,
        name=VERIFIED_ROLE_NAME
    )


    if (
        verified is None
        or verified not in member.roles
    ):

        await interaction.response.send_message(
            "❌ You must be verified first.",
            ephemeral=True
        )

        return


    # =====================================================
    # FILE TYPE
    # =====================================================

    if not allowed_mod_file(
        file.filename
    ):

        allowed = ", ".join(
            sorted(
                ALLOWED_MOD_EXTENSIONS
            )
        )

        await interaction.response.send_message(
            (
                "❌ That file type is not allowed.\n\n"
                f"Allowed: `{allowed}`"
            ),
            ephemeral=True
        )

        return


    # =====================================================
    # 10 MINUTE SUBMISSION COOLDOWN
    # =====================================================

    last_submit = get_mod_cooldown(
        guild.id,
        member.id
    )


    if last_submit:

        next_allowed = last_submit + timedelta(
            seconds=MOD_SUBMIT_COOLDOWN_SECONDS
        )


        if discord.utils.utcnow() < next_allowed:

            remaining = (
                next_allowed
                - discord.utils.utcnow()
            )

            seconds = int(
                remaining.total_seconds()
            )

            await interaction.response.send_message(
                (
                    "⏱️ You can only submit one mod "
                    "every **10 minutes**.\n\n"
                    f"Try again in about `{seconds}` seconds."
                ),
                ephemeral=True
            )

            return


    review_channel = discord.utils.get(
        guild.text_channels,
        name=MOD_REVIEW_CHANNEL_NAME
    )


    if review_channel is None:

        await interaction.response.send_message(
            "❌ Mod Review channel is missing. Ask an admin to run `/setup`.",
            ephemeral=True
        )

        return


    await interaction.response.defer(
        ephemeral=True
    )


    try:

        uploaded_file = await file.to_file()

    except Exception:

        await interaction.followup.send(
            "❌ I couldn't read that file.",
            ephemeral=True
        )

        return


    embed = discord.Embed(
        title="🔎 New Mod Submission",
        description=(
            f"**Mod:** {name}\n\n"
            f"**Description:**\n{description}\n\n"
            f"**Submitted by:** {member.mention}\n"
            f"**User ID:** `{member.id}`"
        ),
        color=discord.Color.yellow(),
        timestamp=discord.utils.utcnow()
    )


    review_message = await review_channel.send(
        embed=embed,
        file=uploaded_file
    )


    await review_message.edit(
        content=(
            f"SUBMISSION_USER_ID={member.id}\n"
            f"SUBMISSION_NAME={name}"
        )
    )


    set_mod_cooldown(
        guild.id,
        member.id
    )


    await interaction.followup.send(
        (
            "✅ Your mod has been submitted for staff review.\n\n"
            "It will only appear in Shared Mods if staff approves it."
        ),
        ephemeral=True
    )


# =========================================================
# /APPROVEMOD
# =========================================================

@tree.command(
    name="approvemod",
    description="Approve a mod submission"
)
@app_commands.describe(
    message_id="Message ID from the private Mod Review channel"
)
@app_commands.checks.has_permissions(
    manage_messages=True
)
async def approvemod(
    interaction,
    message_id: str
):

    guild = interaction.guild

    if guild is None:
        return


    review_channel = discord.utils.get(
        guild.text_channels,
        name=MOD_REVIEW_CHANNEL_NAME
    )


    shared_mods = discord.utils.get(
        guild.forums,
        name=SHARED_MODS_NAME
    )


    if (
        review_channel is None
        or shared_mods is None
    ):

        await interaction.response.send_message(
            "❌ Setup is missing.",
            ephemeral=True
        )

        return


    try:

        review_message = await review_channel.fetch_message(
            int(message_id)
        )

    except Exception:

        await interaction.response.send_message(
            "❌ I couldn't find that review message.",
            ephemeral=True
        )

        return


    if not review_message.attachments:

        await interaction.response.send_message(
            "❌ That submission has no file.",
            ephemeral=True
        )

        return


    # =====================================================
    # READ NAME / USER
    # =====================================================

    content = review_message.content or ""

    user_match = re.search(
        r"SUBMISSION_USER_ID=(\d+)",
        content
    )

    name_match = re.search(
        r"SUBMISSION_NAME=(.+)",
        content
    )


    if not user_match:

        await interaction.response.send_message(
            "❌ Couldn't find submitter information.",
            ephemeral=True
        )

        return


    submitter_id = int(
        user_match.group(1)
    )


    mod_name = (
        name_match.group(1)
        if name_match
        else "Approved Mod"
    )


    attachment = review_message.attachments[0]


    await interaction.response.defer(
        ephemeral=True
    )


    try:

        mod_file = await attachment.to_file()


        thread_with_message = await shared_mods.create_thread(
            name=mod_name[:100],

            content=(
                "⚠️ **COMMUNITY MOD — USE AT YOUR OWN RISK**\n\n"
                f"Submitted by <@{submitter_id}>.\n"
                f"Approved by {interaction.user.mention}.\n\n"
                "SSP Modding Hub does not guarantee that "
                "community-uploaded files are safe."
            ),

            file=mod_file,

            slowmode_delay=SHARED_MOD_COMMENT_SLOWMODE
        )


        try:

            thread = thread_with_message.thread

        except AttributeError:

            thread = thread_with_message


        embed = review_message.embeds[0] if review_message.embeds else None


        if embed:

            embed.color = discord.Color.green()

            embed.add_field(
                name="Status",
                value=(
                    f"✅ Approved by {interaction.user.mention}"
                ),
                inline=False
            )


            await review_message.edit(
                embed=embed
            )


        member = guild.get_member(
            submitter_id
        )


        if member:

            try:

                await member.send(
                    (
                        f"✅ Your mod **{mod_name}** was approved "
                        f"in **{guild.name}**!"
                    )
                )

            except Exception:

                pass


        await mod_log(
            guild,
            "✅ Mod Approved",
            (
                f"Mod: **{mod_name}**\n"
                f"Submitter: <@{submitter_id}>\n"
                f"Approved by: {interaction.user.mention}"
            ),
            discord.Color.green()
        )


        await interaction.followup.send(
            (
                f"✅ **{mod_name}** has been published "
                "to Shared Mods."
            ),
            ephemeral=True
        )


    except Exception as error:

        print(
            "APPROVE ERROR:",
            repr(error)
        )


        await interaction.followup.send(
            (
                "❌ Couldn't publish the mod.\n"
                "Check Railway logs for the exact error."
            ),
            ephemeral=True
        )


# =========================================================
# /REJECTMOD
# =========================================================

@tree.command(
    name="rejectmod",
    description="Reject a mod submission"
)
@app_commands.describe(
    message_id="Message ID from Mod Review",
    reason="Why the mod was rejected"
)
@app_commands.checks.has_permissions(
    manage_messages=True
)
async def rejectmod(
    interaction,
    message_id: str,
    reason: str
):

    guild = interaction.guild

    review_channel = discord.utils.get(
        guild.text_channels,
        name=MOD_REVIEW_CHANNEL_NAME
    )


    if review_channel is None:

        await interaction.response.send_message(
            "❌ Mod Review channel missing.",
            ephemeral=True
        )

        return


    try:

        message = await review_channel.fetch_message(
            int(message_id)
        )

    except Exception:

        await interaction.response.send_message(
            "❌ Submission not found.",
            ephemeral=True
        )

        return


    user_match = re.search(
        r"SUBMISSION_USER_ID=(\d+)",
        message.content or ""
    )


    name_match = re.search(
        r"SUBMISSION_NAME=(.+)",
        message.content or ""
    )


    submitter_id = (
        int(user_match.group(1))
        if user_match
        else None
    )


    mod_name = (
        name_match.group(1)
        if name_match
        else "Mod"
    )


    if message.embeds:

        embed = message.embeds[0]

        embed.color = discord.Color.red()

        embed.add_field(
            name="Status",
            value=(
                f"❌ Rejected by {interaction.user.mention}\n"
                f"Reason: {reason}"
            ),
            inline=False
        )


        await message.edit(
            embed=embed
        )


    if submitter_id:

        member = guild.get_member(
            submitter_id
        )


        if member:

            try:

                await member.send(
                    (
                        f"❌ Your mod **{mod_name}** was rejected.\n\n"
                        f"Reason: {reason}"
                    )
                )

            except Exception:

                pass


    await mod_log(
        guild,
        "❌ Mod Rejected",
        (
            f"Mod: **{mod_name}**\n"
            f"Reason: {reason}\n"
            f"Rejected by: {interaction.user.mention}"
        ),
        discord.Color.red()
    )


    await interaction.response.send_message(
        "❌ Mod rejected.",
        ephemeral=True
    )


# =========================================================
# /WARN
# =========================================================

@tree.command(
    name="warn",
    description="Warn a member"
)
@app_commands.describe(
    member="Member to warn",
    reason="Reason for warning"
)
@app_commands.checks.has_permissions(
    manage_messages=True
)
async def warn(
    interaction,
    member: discord.Member,
    reason: str
):

    add_user_warning(
        interaction.guild.id,
        member.id,
        interaction.user.id,
        reason
    )


    count = len(
        get_user_warnings(
            interaction.guild.id,
            member.id
        )
    )


    try:

        await member.send(
            (
                f"⚠️ You were warned in "
                f"**{interaction.guild.name}**.\n\n"
                f"Reason: {reason}\n"
                f"Total warnings: {count}"
            )
        )

    except Exception:

        pass


    await mod_log(
        interaction.guild,
        "⚠️ Member Warned",
        (
            f"Member: {member.mention}\n"
            f"Moderator: {interaction.user.mention}\n"
            f"Reason: {reason}\n"
            f"Warnings: {count}"
        )
    )


    await interaction.response.send_message(
        (
            f"⚠️ Warned {member.mention}.\n"
            f"They now have **{count}** warning(s)."
        ),
        ephemeral=True
    )


# =========================================================
# /WARNINGS
# =========================================================

@tree.command(
    name="warnings",
    description="Check a member's warnings"
)
@app_commands.describe(
    member="Member to check"
)
@app_commands.checks.has_permissions(
    manage_messages=True
)
async def warnings(
    interaction,
    member: discord.Member
):

    records = get_user_warnings(
        interaction.guild.id,
        member.id
    )


    if not records:

        await interaction.response.send_message(
            f"✅ {member.mention} has no warnings.",
            ephemeral=True
        )

        return


    lines = []


    for index, record in enumerate(
        records,
        start=1
    ):

        lines.append(
            (
                f"**{index}.** {record.get('reason', 'No reason')}\n"
                f"Moderator: <@{record.get('moderator')}>"
            )
        )


    embed = discord.Embed(
        title=f"⚠️ Warnings — {member}",
        description="\n\n".join(lines),
        color=discord.Color.orange()
    )


    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


# =========================================================
# /CLEARWARNINGS
# =========================================================

@tree.command(
    name="clearwarnings",
    description="Clear a member's warnings"
)
@app_commands.describe(
    member="Member whose warnings should be cleared"
)
@app_commands.checks.has_permissions(
    manage_messages=True
)
async def clearwarnings(
    interaction,
    member: discord.Member
):

    clear_user_warnings(
        interaction.guild.id,
        member.id
    )


    await mod_log(
        interaction.guild,
        "🧹 Warnings Cleared",
        (
            f"Member: {member.mention}\n"
            f"Moderator: {interaction.user.mention}"
        )
    )


    await interaction.response.send_message(
        f"✅ Cleared warnings for {member.mention}.",
        ephemeral=True
    )


# =========================================================
# /TIMEOUT
# =========================================================

@tree.command(
    name="timeout",
    description="Timeout a member"
)
@app_commands.describe(
    member="Member to timeout",
    minutes="Number of minutes",
    reason="Reason"
)
@app_commands.checks.has_permissions(
    moderate_members=True
)
async def timeout_command(
    interaction,
    member: discord.Member,
    minutes: app_commands.Range[int, 1, 40320],
    reason: str = "No reason provided"
):

    try:

        await member.timeout(
            timedelta(
                minutes=minutes
            ),
            reason=reason
        )


        await mod_log(
            interaction.guild,
            "⏱️ Manual Timeout",
            (
                f"Member: {member.mention}\n"
                f"Moderator: {interaction.user.mention}\n"
                f"Length: {minutes} minutes\n"
                f"Reason: {reason}"
            )
        )


        await interaction.response.send_message(
            (
                f"✅ Timed out {member.mention} "
                f"for **{minutes} minutes**."
            ),
            ephemeral=True
        )


    except discord.Forbidden:

        await interaction.response.send_message(
            "❌ I cannot timeout that member.",
            ephemeral=True
        )


# =========================================================
# /BAN
# =========================================================

@tree.command(
    name="ban",
    description="Ban a member"
)
@app_commands.describe(
    member="Member to ban",
    reason="Reason"
)
@app_commands.checks.has_permissions(
    ban_members=True
)
async def ban(
    interaction,
    member: discord.Member,
    reason: str = "No reason provided"
):

    try:

        await member.ban(
            reason=reason
        )


        await mod_log(
            interaction.guild,
            "🔨 Member Banned",
            (
                f"Member: {member}\n"
                f"Moderator: {interaction.user.mention}\n"
                f"Reason: {reason}"
            ),
            discord.Color.red()
        )


        await interaction.response.send_message(
            f"🔨 Banned **{member}**.",
            ephemeral=True
        )


    except discord.Forbidden:

        await interaction.response.send_message(
            "❌ I cannot ban that member.",
            ephemeral=True
        )


# =========================================================
# /PURGE
# =========================================================

@tree.command(
    name="purge",
    description="Delete multiple messages"
)
@app_commands.describe(
    amount="Number of messages to delete"
)
@app_commands.checks.has_permissions(
    manage_messages=True
)
async def purge(
    interaction,
    amount: app_commands.Range[int, 1, 100]
):

    channel = interaction.channel


    if not isinstance(
        channel,
        discord.TextChannel
    ):

        await interaction.response.send_message(
            "❌ Use this in a normal text channel.",
            ephemeral=True
        )

        return


    await interaction.response.defer(
        ephemeral=True
    )


    deleted = await channel.purge(
        limit=amount
    )


    await interaction.followup.send(
        f"🧹 Deleted **{len(deleted)}** messages.",
        ephemeral=True
    )


# =========================================================
# /LOCKDOWN
# =========================================================

@tree.command(
    name="lockdown",
    description="Lock General and verification"
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def lockdown(
    interaction
):

    guild = interaction.guild

    raid_lockdowns.add(
        guild.id
    )


    general = discord.utils.get(
        guild.text_channels,
        name=GENERAL_CHANNEL_NAME
    )


    verified = discord.utils.get(
        guild.roles,
        name=VERIFIED_ROLE_NAME
    )


    if (
        general
        and verified
    ):

        overwrite = general.overwrites_for(
            verified
        )

        overwrite.send_messages = False


        await general.set_permissions(
            verified,
            overwrite=overwrite,
            reason="Manual lockdown"
        )


    await mod_log(
        guild,
        "🔒 Manual Lockdown",
        (
            f"Started by {interaction.user.mention}"
        ),
        discord.Color.red()
    )


    await interaction.response.send_message(
        "🔒 Server verification/general lockdown activated.",
        ephemeral=True
    )


# =========================================================
# /UNLOCK
# =========================================================

@tree.command(
    name="unlock",
    description="Disable raid lockdown"
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def unlock(
    interaction
):

    guild = interaction.guild


    raid_lockdowns.discard(
        guild.id
    )


    general = discord.utils.get(
        guild.text_channels,
        name=GENERAL_CHANNEL_NAME
    )


    verified = discord.utils.get(
        guild.roles,
        name=VERIFIED_ROLE_NAME
    )


    if (
        general
        and verified
    ):

        await general.set_permissions(
            verified,

            view_channel=True,
            send_messages=True,

            attach_files=False,
            embed_links=False,

            add_reactions=False,

            create_public_threads=False,
            create_private_threads=False,
            send_messages_in_threads=False,

            read_message_history=True
        )


    await mod_log(
        guild,
        "🔓 Lockdown Disabled",
        (
            f"Disabled by {interaction.user.mention}"
        ),
        discord.Color.green()
    )


    await interaction.response.send_message(
        "🔓 Raid lockdown disabled.",
        ephemeral=True
    )


# =========================================================
# /UNVERIFY
# =========================================================

@tree.command(
    name="unverify",
    description="Remove Verified from a member"
)
@app_commands.describe(
    member="Member to unverify"
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def unverify(
    interaction,
    member: discord.Member
):

    role = discord.utils.get(
        interaction.guild.roles,
        name=VERIFIED_ROLE_NAME
    )


    if (
        role is None
        or role not in member.roles
    ):

        await interaction.response.send_message(
            "⚠️ That member is not verified.",
            ephemeral=True
        )

        return


    await member.remove_roles(
        role,
        reason=f"Unverified by {interaction.user}"
    )


    await mod_log(
        interaction.guild,
        "❌ Member Unverified",
        (
            f"Member: {member.mention}\n"
            f"Moderator: {interaction.user.mention}"
        )
    )


    await interaction.response.send_message(
        f"✅ Removed Verified from {member.mention}.",
        ephemeral=True
    )


# =========================================================
# COMMAND ERROR HANDLER
# =========================================================

@tree.error
async def command_error(
    interaction,
    error
):

    print("")
    print("======================================")
    print("COMMAND ERROR")
    print("======================================")
    print(
        repr(error)
    )


    if hasattr(
        error,
        "original"
    ):

        print(
            "ORIGINAL:",
            repr(error.original)
        )


    print("======================================")
    print("")


    if isinstance(
        error,
        app_commands.MissingPermissions
    ):

        text = (
            "❌ You don't have permission to use that command."
        )

    else:

        text = (
            "❌ Something went wrong. "
            "Check the Railway logs."
        )


    try:

        if interaction.response.is_done():

            await interaction.followup.send(
                text,
                ephemeral=True
            )

        else:

            await interaction.response.send_message(
                text,
                ephemeral=True
            )

    except Exception:

        pass


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    if not TOKEN:

        raise RuntimeError(
            " is missing. "
            "Add it in Railway Variables."
        )


    client.run(
        TOKEN
    )