import os
import re
import asyncio
from collections import defaultdict, deque
from datetime import timedelta

import discord
from discord import app_commands


# =========================================================
# SETTINGS
# =========================================================

TOKEN = os.getenv("DISCORD_BOT_TOKEN")

VERIFIED_ROLE = "Verified"

CATEGORY_NAME = "✅ VERIFICATION"

RULES_CHANNEL = "📜・rules"
VERIFY_CHANNEL = "✅・verification"
GENERAL_CHANNEL = "💬・general"
MOD_LOG_CHANNEL = "🛡️・mod-logs"

SHARED_MODS_CHANNEL = "🧩・shared-mods"


# =========================================================
# COOLDOWNS
# =========================================================

# General chat
GENERAL_SLOWMODE = 10

# Shared Mods:
# 600 seconds = 10 minutes between NEW mod posts
MOD_POST_COOLDOWN = 600

# 10 seconds between comments inside a mod post
MOD_COMMENT_SLOWMODE = 10


# =========================================================
# MODERATION
# =========================================================

BAD_WORD_TIMEOUT = 30

REPEAT_TIMEOUT = 10
REPEAT_LIMIT = 3

SPAM_TIMEOUT = 10
SPAM_MESSAGE_LIMIT = 6
SPAM_WINDOW_SECONDS = 8


# =========================================================
# RAID PROTECTION
# =========================================================

RAID_JOIN_LIMIT = 6
RAID_JOIN_WINDOW = 10

NEW_ACCOUNT_HOURS = 24


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

tree = app_commands.CommandTree(client)


# =========================================================
# MEMORY
# =========================================================

recent_messages = defaultdict(
    lambda: deque(
        maxlen=REPEAT_LIMIT
    )
)

message_times = defaultdict(
    deque
)

recent_joins = deque()

raid_lockdowns = set()

view_registered = False


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


# Common spellings / obfuscations of racial slur

NWORD_PATTERN = re.compile(
    r"\bn[\W_]*[i1!][\W_]*g[\W_]*g[\W_]*"
    r"[e3a@][\W_]*r?s?\b",
    re.IGNORECASE
)


# Discord invites

INVITE_PATTERN = re.compile(
    r"(?:https?://)?"
    r"(?:www\.)?"
    r"(?:discord\.gg|discord(?:app)?\.com/invite)"
    r"/[A-Za-z0-9-]+",
    re.IGNORECASE
)


# GIF links

GIF_PATTERN = re.compile(
    r"(?:https?://\S+\.gif(?:\?\S*)?$)|"
    r"(?:https?://)?"
    r"(?:www\.)?"
    r"(?:tenor\.com|giphy\.com|media\.giphy\.com)"
    r"/\S+",
    re.IGNORECASE
)


# Any URL

URL_PATTERN = re.compile(
    r"https?://\S+",
    re.IGNORECASE
)


# =========================================================
# HELPERS
# =========================================================

def normalize_text(text):

    text = text.lower().strip()

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text


def contains_bad_language(text):

    lower = text.lower()

    if NWORD_PATTERN.search(text):
        return True

    for phrase in BAD_PHRASES:

        if phrase in lower:
            return True

    return False


def is_staff(member):

    permissions = member.guild_permissions

    return (
        permissions.administrator
        or permissions.manage_guild
        or permissions.manage_messages
        or permissions.moderate_members
    )


async def delete_message(message):

    try:

        await message.delete()

    except (
        discord.Forbidden,
        discord.NotFound
    ):

        pass


async def warning_message(
    channel,
    member,
    text
):

    try:

        msg = await channel.send(
            f"{member.mention} {text}"
        )

        await asyncio.sleep(7)

        await msg.delete()

    except Exception:

        pass


async def send_dm(
    member,
    text
):

    try:

        await member.send(
            text
        )

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
    description
):

    channel = discord.utils.get(
        guild.text_channels,
        name=MOD_LOG_CHANNEL
    )

    if channel is None:
        return

    embed = discord.Embed(
        title=title,
        description=description,
        color=discord.Color.orange()
    )

    try:

        await channel.send(
            embed=embed
        )

    except Exception:

        pass


# =========================================================
# SPAM CHECK
# =========================================================

async def check_spam(
    message,
    scope
):

    member = message.author
    guild = message.guild

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


    # =====================================================
    # FAST SPAM
    # =====================================================

    if len(times) >= SPAM_MESSAGE_LIMIT:

        times.clear()

        await delete_message(
            message
        )

        success = await timeout_member(
            member,
            SPAM_TIMEOUT,
            "Message spam"
        )

        if success:

            await warning_message(
                message.channel,
                member,
                "⚠️ Spam detected. "
                "You have been timed out for **10 minutes**."
            )

        await mod_log(
            guild,
            "⚠️ Spam timeout",
            (
                f"User: {member.mention}\n"
                f"Reason: {SPAM_MESSAGE_LIMIT}+ messages "
                f"in {SPAM_WINDOW_SECONDS} seconds\n"
                f"Timeout: {SPAM_TIMEOUT} minutes"
            )
        )

        return True


    # =====================================================
    # REPEATED COPY-PASTE
    # =====================================================

    text = normalize_text(
        message.content or ""
    )

    if not text:
        return False


    history = recent_messages[key]

    history.append(
        text
    )


    if (
        len(history) == REPEAT_LIMIT
        and len(set(history)) == 1
    ):

        history.clear()

        await delete_message(
            message
        )

        success = await timeout_member(
            member,
            REPEAT_TIMEOUT,
            "Repeated the same message 3 times"
        )

        if success:

            await warning_message(
                message.channel,
                member,
                (
                    "⚠️ **Warning:** you sent the same "
                    "message 3 times in a row.\n"
                    "You have been timed out for "
                    "**10 minutes**."
                )
            )

        await mod_log(
            guild,
            "⚠️ Copy-paste spam",
            (
                f"User: {member.mention}\n"
                "Reason: same message 3 times in a row\n"
                f"Timeout: {REPEAT_TIMEOUT} minutes"
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

    def __init__(self):

        super().__init__(
            timeout=None
        )


    @discord.ui.button(
        label="Verify",
        emoji="✅",
        style=discord.ButtonStyle.green,
        custom_id="ssp_verify_button_v4"
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
            name=VERIFIED_ROLE
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
        # RAID PROTECTION
        # =================================================

        if guild.id in raid_lockdowns:

            age = (
                discord.utils.utcnow()
                - member.created_at
            )

            if age < timedelta(
                hours=NEW_ACCOUNT_HOURS
            ):

                await interaction.response.send_message(
                    (
                        "🛡️ The server is currently under "
                        "raid protection.\n\n"
                        "Very new accounts cannot verify right now."
                    ),
                    ephemeral=True
                )

                return


        bot_member = guild.me


        if bot_member is None:
            return


        if role >= bot_member.top_role:

            await interaction.response.send_message(
                (
                    "❌ My bot role needs to be ABOVE "
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


            await interaction.response.send_message(
                (
                    "✅ **Verified!**\n\n"
                    "You can now access:\n"
                    "💬・general\n"
                    "🧩・shared-mods"
                ),
                ephemeral=True
            )


        except discord.Forbidden:

            await interaction.response.send_message(
                "❌ I need Manage Roles permission.",
                ephemeral=True
            )


# =========================================================
# READY
# =========================================================

@client.event
async def on_ready():

    global view_registered


    if not view_registered:

        client.add_view(
            VerifyView()
        )

        view_registered = True


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


    # Staff bypass filters

    if is_staff(member):
        return


    rules = discord.utils.get(
        guild.text_channels,
        name=RULES_CHANNEL
    )


    verification = discord.utils.get(
        guild.text_channels,
        name=VERIFY_CHANNEL
    )


    general = discord.utils.get(
        guild.text_channels,
        name=GENERAL_CHANNEL
    )


    # =====================================================
    # RULES / VERIFICATION = READ ONLY
    # =====================================================

    if message.channel in (
        rules,
        verification
    ):

        await delete_message(
            message
        )

        return


    # =====================================================
    # SHARED MODS FORUM
    # =====================================================

    if isinstance(
        message.channel,
        discord.Thread
    ):

        parent = message.channel.parent


        if (
            isinstance(
                parent,
                discord.ForumChannel
            )
            and parent.name == SHARED_MODS_CHANNEL
        ):

            # =============================================
            # BAD LANGUAGE
            # =============================================

            if contains_bad_language(
                message.content or ""
            ):

                await delete_message(
                    message
                )

                success = await timeout_member(
                    member,
                    BAD_WORD_TIMEOUT,
                    "Prohibited language in Shared Mods"
                )

                if success:

                    await warning_message(
                        message.channel,
                        member,
                        (
                            "🚫 Prohibited language is not allowed. "
                            "You have been timed out for **30 minutes**."
                        )
                    )


                await mod_log(
                    guild,
                    "🚫 Shared Mods timeout",
                    (
                        f"User: {member.mention}\n"
                        "Reason: prohibited language\n"
                        "Timeout: 30 minutes"
                    )
                )

                return


            # =============================================
            # DISCORD INVITES
            # =============================================

            if INVITE_PATTERN.search(
                message.content or ""
            ):

                await delete_message(
                    message
                )

                await warning_message(
                    message.channel,
                    member,
                    "⚠️ Discord invites are not allowed here."
                )

                return


            # =============================================
            # EXTERNAL LINKS
            # =============================================

            if URL_PATTERN.search(
                message.content or ""
            ):

                await delete_message(
                    message
                )

                await warning_message(
                    message.channel,
                    member,
                    (
                        "⚠️ Upload the mod directly as a file. "
                        "External links are not allowed."
                    )
                )

                return


            # =============================================
            # STARTER MESSAGE
            #
            # Forum starter message ID matches thread ID.
            # It MUST contain exactly one file.
            # =============================================

            starter_message = (
                message.id
                == message.channel.id
            )


            if starter_message:

                if len(
                    message.attachments
                ) != 1:

                    await send_dm(
                        member,
                        (
                            "❌ Your Shared Mods post was removed.\n\n"
                            "Every mod post must contain "
                            "**exactly one file**.\n\n"
                            "Create the post again with a title "
                            "and one attached mod file."
                        )
                    )


                    await mod_log(
                        guild,
                        "🗑️ Invalid mod post removed",
                        (
                            f"User: {member.mention}\n"
                            f"Post: {message.channel.name}\n"
                            "Reason: post did not contain exactly one file"
                        )
                    )


                    try:

                        await message.channel.delete(
                            reason=(
                                "Shared Mods posts require exactly one file"
                            )
                        )

                    except discord.Forbidden:

                        pass


                    return


            # =============================================
            # REPLIES CANNOT CONTAIN EXTRA FILES
            # =============================================

            else:

                if message.attachments:

                    await delete_message(
                        message
                    )

                    await warning_message(
                        message.channel,
                        member,
                        (
                            "⚠️ Only the original mod post may "
                            "contain a file. Replies are text-only."
                        )
                    )

                    return


            # =============================================
            # SPAM PROTECTION
            # =============================================

            spammed = await check_spam(
                message,
                "shared_mods"
            )

            if spammed:
                return


            return


    # =========================================================
    # GENERAL
    # =========================================================

    if general is None:
        return


    if message.channel.id != general.id:
        return


    text = message.content or ""


    # =====================================================
    # TEXT ONLY
    # =====================================================

    if message.attachments:

        await delete_message(
            message
        )

        await warning_message(
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

        await delete_message(
            message
        )

        await warning_message(
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

        await delete_message(
            message
        )

        await warning_message(
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

        await delete_message(
            message
        )

        await warning_message(
            message.channel,
            member,
            "⚠️ Discord invites are not allowed."
        )

        return


    # =====================================================
    # LINKS
    # =====================================================

    if URL_PATTERN.search(
        text
    ):

        await delete_message(
            message
        )

        await warning_message(
            message.channel,
            member,
            "⚠️ Links are not allowed in general."
        )

        return


    # =====================================================
    # BAD LANGUAGE
    # =====================================================

    if contains_bad_language(
        text
    ):

        await delete_message(
            message
        )


        success = await timeout_member(
            member,
            BAD_WORD_TIMEOUT,
            "Prohibited language / harassment"
        )


        if success:

            await warning_message(
                message.channel,
                member,
                (
                    "🚫 Prohibited language is not allowed. "
                    "You have been timed out for **30 minutes**."
                )
            )


        await mod_log(
            guild,
            "🚫 30-minute timeout",
            (
                f"User: {member.mention}\n"
                "Reason: prohibited language / harassment\n"
                "Timeout: 30 minutes"
            )
        )

        return


    # =====================================================
    # SPAM
    # =====================================================

    spammed = await check_spam(
        message,
        "general"
    )

    if spammed:
        return


# =========================================================
# RAID DETECTION
# =========================================================

@client.event
async def on_member_join(
    member
):

    now = discord.utils.utcnow()


    recent_joins.append(
        now
    )


    cutoff = now - timedelta(
        seconds=RAID_JOIN_WINDOW
    )


    while (
        recent_joins
        and recent_joins[0] < cutoff
    ):

        recent_joins.popleft()


    if len(
        recent_joins
    ) < RAID_JOIN_LIMIT:

        return


    guild = member.guild


    if guild.id in raid_lockdowns:
        return


    raid_lockdowns.add(
        guild.id
    )


    general = discord.utils.get(
        guild.text_channels,
        name=GENERAL_CHANNEL
    )


    verified = discord.utils.get(
        guild.roles,
        name=VERIFIED_ROLE
    )


    if (
        general is not None
        and verified is not None
    ):

        try:

            overwrite = general.overwrites_for(
                verified
            )

            overwrite.view_channel = True
            overwrite.send_messages = False


            await general.set_permissions(
                verified,
                overwrite=overwrite,
                reason="Automatic raid lockdown"
            )

        except discord.Forbidden:

            pass


    await mod_log(
        guild,
        "🚨 RAID DETECTED",
        (
            f"{RAID_JOIN_LIMIT}+ accounts joined within "
            f"{RAID_JOIN_WINDOW} seconds.\n\n"
            "`general` has automatically been locked.\n\n"
            "Use `/unlock` when it is safe."
        )
    )


# =========================================================
# /PING
# =========================================================

@tree.command(
    name="ping",
    description="Check if the SSP bot is online"
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
    description="Create SSP verification, moderation and Shared Mods"
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
            "❌ Use this inside your server.",
            ephemeral=True
        )

        return


    await interaction.response.defer(
        ephemeral=True
    )


    # =====================================================
    # CHECK EXISTING SETUP
    # =====================================================

    existing = discord.utils.get(
        guild.categories,
        name=CATEGORY_NAME
    )


    if existing:

        await interaction.followup.send(
            (
                "⚠️ The setup already exists.\n\n"
                "Delete the old `✅ VERIFICATION` category "
                "before running `/setup` again."
            ),
            ephemeral=True
        )

        return


    bot_member = guild.me


    if bot_member is None:

        await interaction.followup.send(
            "❌ I could not check my permissions.",
            ephemeral=True
        )

        return


    # =====================================================
    # PERMISSION CHECK
    # =====================================================

    permissions = bot_member.guild_permissions

    missing = []


    if not permissions.manage_channels:
        missing.append(
            "Manage Channels"
        )


    if not permissions.manage_roles:
        missing.append(
            "Manage Roles"
        )


    if not permissions.manage_messages:
        missing.append(
            "Manage Messages"
        )


    if not permissions.moderate_members:
        missing.append(
            "Moderate Members"
        )


    if missing:

        await interaction.followup.send(
            (
                "❌ I am missing these permissions:\n\n"
                + "\n".join(
                    f"• {permission}"
                    for permission in missing
                )
            ),
            ephemeral=True
        )

        return


    # =====================================================
    # VERIFIED ROLE
    # =====================================================

    verified = discord.utils.get(
        guild.roles,
        name=VERIFIED_ROLE
    )


    if verified is None:

        verified = await guild.create_role(
            name=VERIFIED_ROLE,
            reason="SSP verification"
        )


    everyone = guild.default_role


    # =====================================================
    # CATEGORY
    # =====================================================

    category = await guild.create_category(
        CATEGORY_NAME,
        reason="SSP setup"
    )


    # =====================================================
    # NORMAL CHANNELS
    # =====================================================

    rules = await guild.create_text_channel(
        RULES_CHANNEL,
        category=category
    )


    verify = await guild.create_text_channel(
        VERIFY_CHANNEL,
        category=category
    )


    general = await guild.create_text_channel(
        GENERAL_CHANNEL,
        category=category,
        slowmode_delay=GENERAL_SLOWMODE
    )


    logs = await guild.create_text_channel(
        MOD_LOG_CHANNEL,
        category=category
    )


    # =====================================================
    # SHARED MODS FORUM
    # =====================================================
    #
    # slowmode_delay=600:
    # one new forum post every 10 minutes
    #
    # default_thread_slowmode_delay=10:
    # 10 seconds between messages in each post
    #

    forum_overwrites = {

        everyone: discord.PermissionOverwrite(
            view_channel=False,
            send_messages=False,
            create_public_threads=False
        ),

        verified: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            create_public_threads=True,
            send_messages_in_threads=True,
            attach_files=True,
            embed_links=False,
            read_message_history=True
        )
    }


    shared_mods = await guild.create_forum(
        name=SHARED_MODS_CHANNEL,

        category=category,

        topic=(
            "⚠️ WARNING: Do not automatically trust every mod "
            "shared here. Files are uploaded by community members. "
            "Only download files you are comfortable using."
        ),

        slowmode_delay=MOD_POST_COOLDOWN,

        default_thread_slowmode_delay=MOD_COMMENT_SLOWMODE,

        overwrites=forum_overwrites,

        reason="SSP Shared Mods forum"
    )


    # =====================================================
    # RULES PERMISSIONS
    # =====================================================

    await rules.set_permissions(
        everyone,

        view_channel=False,
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

        view_channel=False,
        send_messages=False,
        add_reactions=False,

        create_public_threads=False,
        create_private_threads=False,
        send_messages_in_threads=False
    )


    # =====================================================
    # GENERAL PERMISSIONS
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


    # =====================================================
    # MOD LOGS
    # =====================================================

    await logs.set_permissions(
        everyone,
        view_channel=False
    )


    await logs.set_permissions(
        verified,
        view_channel=False
    )


    # =====================================================
    # RULES MESSAGE
    # =====================================================

    rules_embed = discord.Embed(
        title="📜 SSP Modding Hub Rules",

        description=(
            "Welcome to **SSP Modding Hub!**\n\n"

            "• No spam.\n"
            "• No repeated copy-paste messages.\n"
            "• No GIFs, files, or images in general.\n"
            "• No Discord invites in general.\n"
            "• No links in general.\n"
            "• No harassment or slurs.\n"
            "• Do not tell people to hurt themselves.\n"
            "• Be respectful.\n"
            "• Follow Discord's rules.\n\n"

            "💬 `general` has a **10-second cooldown**.\n\n"

            "🧩 **Shared Mods:**\n"
            "• Verified members only.\n"
            "• One new mod post every **10 minutes**.\n"
            "• Every mod post must have **exactly one file**.\n"
            "• Replies are text-only.\n"
            "• Comments have a **10-second cooldown**.\n"
            "• Do not automatically trust files shared by members."
        ),

        color=discord.Color.blue()
    )


    await rules.send(
        embed=rules_embed
    )


    # =====================================================
    # VERIFICATION MESSAGE
    # =====================================================

    verify_embed = discord.Embed(
        title="✅ Verification",

        description=(
            "Press **✅ Verify** below.\n\n"

            "After verification you will unlock:\n"
            "💬・general\n"
            "🧩・shared-mods\n\n"

            "You cannot send messages, reactions, files, "
            "or anything else in this verification channel."
        ),

        color=discord.Color.green()
    )


    await verify.send(
        embed=verify_embed,
        view=VerifyView()
    )


    # =====================================================
    # SHARED MODS WARNING POST
    # =====================================================

    try:

        await shared_mods.create_thread(
            name="⚠️ READ BEFORE DOWNLOADING MODS",

            content=(
                "⚠️ **DO NOT TRUST EVERY MOD SHARED HERE**\n\n"
                "Mods in this forum are uploaded by community members. "
                "SSP Modding Hub does not automatically guarantee that "
                "every uploaded file is safe.\n\n"
                "Only download and run files you are comfortable using.\n\n"
                "**Posting rules:**\n"
                "• One mod post every 10 minutes\n"
                "• Exactly one file per new mod post\n"
                "• Give your post a clear name/title\n"
                "• Replies are text-only\n"
                "• No spam\n"
                "• No Discord invites or external download links"
            )
        )

    except Exception as error:

        print(
            "WARNING POST ERROR:",
            repr(error)
        )


    # =====================================================
    # DONE
    # =====================================================

    await interaction.followup.send(
        (
            "✅ **Setup complete!**\n\n"

            "Created:\n"
            "👤 `Verified` role\n"
            "📜 `rules`\n"
            "✅ `verification`\n"
            "💬 `general`\n"
            "🧩 `shared-mods` **Forum**\n"
            "🛡️ `mod-logs`\n\n"

            "Shared Mods:\n"
            "📁 Exactly 1 file per mod post\n"
            "⏱️ 10 minutes between new mod posts\n"
            "💬 10 seconds between comments\n"
            "🔒 Verified members only\n\n"

            "Run `/showsetup` when ready."
        ),

        ephemeral=True
    )


# =========================================================
# /SHOWSETUP
# =========================================================

@tree.command(
    name="showsetup",
    description="Open SSP verification"
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def showsetup(
    interaction
):

    guild = interaction.guild


    if guild is None:

        await interaction.response.send_message(
            "❌ Use this inside your server.",
            ephemeral=True
        )

        return


    rules = discord.utils.get(
        guild.text_channels,
        name=RULES_CHANNEL
    )


    verify = discord.utils.get(
        guild.text_channels,
        name=VERIFY_CHANNEL
    )


    general = discord.utils.get(
        guild.text_channels,
        name=GENERAL_CHANNEL
    )


    shared_mods = discord.utils.get(
        guild.forums,
        name=SHARED_MODS_CHANNEL
    )


    verified = discord.utils.get(
        guild.roles,
        name=VERIFIED_ROLE
    )


    if not all([
        rules,
        verify,
        general,
        shared_mods,
        verified
    ]):

        await interaction.response.send_message(
            (
                "❌ Setup is incomplete.\n"
                "Delete the old setup and run `/setup`."
            ),
            ephemeral=True
        )

        return


    everyone = guild.default_role


    # =====================================================
    # RULES = VIEW ONLY
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
    # VERIFY = VIEW ONLY
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
    # GENERAL = VERIFIED ONLY
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
        slowmode_delay=GENERAL_SLOWMODE
    )


    # =====================================================
    # SHARED MODS = VERIFIED ONLY
    # =====================================================

    await shared_mods.set_permissions(
        everyone,

        view_channel=False,
        send_messages=False,
        create_public_threads=False
    )


    await shared_mods.set_permissions(
        verified,

        view_channel=True,
        send_messages=True,
        create_public_threads=True,
        send_messages_in_threads=True,

        attach_files=True,
        embed_links=False,

        read_message_history=True
    )


    await shared_mods.edit(
        slowmode_delay=MOD_POST_COOLDOWN,

        default_thread_slowmode_delay=MOD_COMMENT_SLOWMODE
    )


    await interaction.response.send_message(
        (
            "✅ Verification is open.\n\n"
            "Before verification:\n"
            "📜 Rules\n"
            "✅ Verification\n\n"
            "After verification:\n"
            "💬 General\n"
            "🧩 Shared Mods"
        ),
        ephemeral=True
    )


# =========================================================
# /LOCKDOWN
# =========================================================

@tree.command(
    name="lockdown",
    description="Lock general during a raid"
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def lockdown(
    interaction
):

    guild = interaction.guild


    general = discord.utils.get(
        guild.text_channels,
        name=GENERAL_CHANNEL
    )


    verified = discord.utils.get(
        guild.roles,
        name=VERIFIED_ROLE
    )


    if (
        general is None
        or verified is None
    ):

        await interaction.response.send_message(
            "❌ Setup not found.",
            ephemeral=True
        )

        return


    raid_lockdowns.add(
        guild.id
    )


    overwrite = general.overwrites_for(
        verified
    )


    overwrite.send_messages = False


    await general.set_permissions(
        verified,
        overwrite=overwrite
    )


    await interaction.response.send_message(
        "🔒 General locked.",
        ephemeral=True
    )


# =========================================================
# /UNLOCK
# =========================================================

@tree.command(
    name="unlock",
    description="Unlock general after a raid"
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def unlock(
    interaction
):

    guild = interaction.guild


    general = discord.utils.get(
        guild.text_channels,
        name=GENERAL_CHANNEL
    )


    verified = discord.utils.get(
        guild.roles,
        name=VERIFIED_ROLE
    )


    if (
        general is None
        or verified is None
    ):

        await interaction.response.send_message(
            "❌ Setup not found.",
            ephemeral=True
        )

        return


    raid_lockdowns.discard(
        guild.id
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


    await interaction.response.send_message(
        "🔓 General unlocked.",
        ephemeral=True
    )


# =========================================================
# /UNVERIFY
# =========================================================

@tree.command(
    name="unverify",
    description="Remove verification from a member"
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

    guild = interaction.guild


    role = discord.utils.get(
        guild.roles,
        name=VERIFIED_ROLE
    )


    if role is None:

        await interaction.response.send_message(
            "❌ Verified role not found.",
            ephemeral=True
        )

        return


    if role not in member.roles:

        await interaction.response.send_message(
            f"⚠️ {member.mention} is not verified.",
            ephemeral=True
        )

        return


    try:

        await member.remove_roles(
            role,
            reason=f"Unverified by {interaction.user}"
        )


        await interaction.response.send_message(
            f"✅ Removed verification from {member.mention}.",
            ephemeral=True
        )


    except discord.Forbidden:

        await interaction.response.send_message(
            "❌ I cannot manage that member.",
            ephemeral=True
        )


# =========================================================
# ERRORS
# =========================================================

@tree.error
async def command_error(
    interaction,
    error
):

    print("")
    print("================================")
    print("COMMAND ERROR")
    print("================================")
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


    print("================================")
    print("")


    if isinstance(
        error,
        app_commands.MissingPermissions
    ):

        text = (
            "❌ You need Administrator permission."
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
# START BOT
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