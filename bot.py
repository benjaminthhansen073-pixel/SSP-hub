import os
import discord
from discord import app_commands

# =========================================================
# SETTINGS
# =========================================================

TOKEN = os.getenv("DISCORD_BOT_TOKEN")

VERIFIED_ROLE_NAME = "Verified"
CATEGORY_NAME = "✅ VERIFICATION"
RULES_CHANNEL_NAME = "📜・rules"
VERIFY_CHANNEL_NAME = "✅・verification"
GENERAL_CHANNEL_NAME = "💬・general"

# =========================================================
# DISCORD CLIENT
# =========================================================

intents = discord.Intents.default()

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


# =========================================================
# VERIFY BUTTON
# =========================================================

class VerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Verify",
        emoji="✅",
        style=discord.ButtonStyle.green,
        custom_id="ssp_verify_button_v1"
    )
    async def verify_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        guild = interaction.guild

        if guild is None:
            await interaction.response.send_message(
                "❌ Verification only works inside the server.",
                ephemeral=True
            )
            return

        member = interaction.user

        if not isinstance(member, discord.Member):
            await interaction.response.send_message(
                "❌ I couldn't identify your server member account.",
                ephemeral=True
            )
            return

        verified_role = discord.utils.get(
            guild.roles,
            name=VERIFIED_ROLE_NAME
        )

        if verified_role is None:
            await interaction.response.send_message(
                "❌ The Verified role is missing. Ask an administrator to run `/setup`.",
                ephemeral=True
            )
            return

        if verified_role in member.roles:
            await interaction.response.send_message(
                "✅ You are already verified!",
                ephemeral=True
            )
            return

        bot_member = guild.me

        if bot_member is None:
            await interaction.response.send_message(
                "❌ I couldn't check my server permissions.",
                ephemeral=True
            )
            return

        if verified_role >= bot_member.top_role:
            await interaction.response.send_message(
                "❌ I can't give you the Verified role because my bot role is not above it.\n"
                "An admin needs to move my bot role above `Verified` in Server Settings → Roles.",
                ephemeral=True
            )
            return

        try:
            await member.add_roles(
                verified_role,
                reason="SSP verification button"
            )

            await interaction.response.send_message(
                "✅ **You are verified!**\n"
                "You now have access to `💬・general`.",
                ephemeral=True
            )

        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ Discord blocked me from giving the role.\n"
                "Make sure I have **Manage Roles** and my bot role is above `Verified`.",
                ephemeral=True
            )

        except Exception as error:
            print("VERIFY ERROR:", repr(error))

            await interaction.response.send_message(
                "❌ Verification failed. Please tell an administrator.",
                ephemeral=True
            )


# =========================================================
# READY EVENT
# =========================================================

@client.event
async def on_ready():
    # Makes the verify button keep working after restarts.
    client.add_view(VerifyView())

    print("")
    print("==========================================")
    print("✅ SSP MODDING HUB BOT IS ONLINE")
    print("==========================================")
    print(f"Bot: {client.user}")
    print(f"Bot ID: {client.user.id}")
    print(f"Servers: {len(client.guilds)}")

    try:
        synced = await tree.sync()
        print(f"Slash commands synced: {len(synced)}")
    except Exception as error:
        print("COMMAND SYNC ERROR:", repr(error))

    print("==========================================")
    print("")


# =========================================================
# /PING
# =========================================================

@tree.command(
    name="ping",
    description="Check if the SSP bot is online"
)
async def ping(interaction: discord.Interaction):
    latency = round(client.latency * 1000)

    await interaction.response.send_message(
        f"🏓 Pong! `{latency}ms`",
        ephemeral=True
    )


# =========================================================
# /SETUP
# =========================================================

@tree.command(
    name="setup",
    description="Create the SSP verification system"
)
@app_commands.checks.has_permissions(administrator=True)
async def setup(interaction: discord.Interaction):
    guild = interaction.guild

    if guild is None:
        await interaction.response.send_message(
            "❌ Use this command inside your server.",
            ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)

    existing_category = discord.utils.get(
        guild.categories,
        name=CATEGORY_NAME
    )

    if existing_category:
        await interaction.followup.send(
            "⚠️ The verification setup already exists.\n"
            "Delete the old `✅ VERIFICATION` category first if you want to rebuild it.",
            ephemeral=True
        )
        return

    bot_member = guild.me

    if bot_member is None:
        await interaction.followup.send(
            "❌ I couldn't read my own server permissions.",
            ephemeral=True
        )
        return

    required = bot_member.guild_permissions

    if not required.manage_channels:
        await interaction.followup.send(
            "❌ I need **Manage Channels** permission before `/setup` can work.",
            ephemeral=True
        )
        return

    if not required.manage_roles:
        await interaction.followup.send(
            "❌ I need **Manage Roles** permission before `/setup` can work.",
            ephemeral=True
        )
        return

    verified_role = discord.utils.get(
        guild.roles,
        name=VERIFIED_ROLE_NAME
    )

    if verified_role is None:
        verified_role = await guild.create_role(
            name=VERIFIED_ROLE_NAME,
            reason="SSP verification system"
        )

    everyone = guild.default_role

    category_overwrites = {
        everyone: discord.PermissionOverwrite(
            view_channel=False
        ),
        bot_member: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            manage_channels=True,
            read_message_history=True
        )
    }

    category = await guild.create_category(
        name=CATEGORY_NAME,
        overwrites=category_overwrites,
        reason="SSP verification system"
    )

    rules_channel = await guild.create_text_channel(
        name=RULES_CHANNEL_NAME,
        category=category,
        reason="SSP verification system"
    )

    verify_channel = await guild.create_text_channel(
        name=VERIFY_CHANNEL_NAME,
        category=category,
        reason="SSP verification system"
    )

    general_channel = await guild.create_text_channel(
        name=GENERAL_CHANNEL_NAME,
        category=category,
        slowmode_delay=10,
        reason="SSP verification system"
    )

    # Unverified users cannot see any of these until /showsetup.
    await rules_channel.set_permissions(
        everyone,
        view_channel=False,
        send_messages=False
    )

    await verify_channel.set_permissions(
        everyone,
        view_channel=False,
        send_messages=False
    )

    await general_channel.set_permissions(
        everyone,
        view_channel=False,
        send_messages=False
    )

    # Verified users can see and use general.
    await general_channel.set_permissions(
        verified_role,
        view_channel=True,
        send_messages=True,
        read_message_history=True
    )

    rules_embed = discord.Embed(
        title="📜 SSP Modding Hub Rules",
        description="Welcome to **SSP Modding Hub!**\n\nPlease follow the rules below.",
        color=discord.Color.blue()
    )

    rules_embed.add_field(
        name="1️⃣ No Spam",
        value="Do not spam messages, emojis, images, or links.",
        inline=False
    )

    rules_embed.add_field(
        name="2️⃣ No Raiding",
        value="Do not raid or help people raid the server.",
        inline=False
    )

    rules_embed.add_field(
        name="3️⃣ No Ping Spam",
        value="Do not repeatedly ping members or roles.",
        inline=False
    )

    rules_embed.add_field(
        name="4️⃣ Be Respectful",
        value="Treat other members respectfully.",
        inline=False
    )

    rules_embed.add_field(
        name="5️⃣ Follow Discord Rules",
        value="Follow Discord's Terms and Community Guidelines.",
        inline=False
    )

    await rules_channel.send(embed=rules_embed)

    verification_embed = discord.Embed(
        title="✅ Verification",
        description=(
            "Welcome to **SSP Modding Hub!**\n\n"
            "Press the **✅ Verify** button below.\n\n"
            "After verification, you will unlock `💬・general`."
        ),
        color=discord.Color.green()
    )

    await verify_channel.send(
        embed=verification_embed,
        view=VerifyView()
    )

    await interaction.followup.send(
        "✅ **Verification system created!**\n\n"
        "Created:\n"
        "👤 `Verified` role\n"
        "📜 `rules`\n"
        "✅ `verification`\n"
        "💬 `general`\n\n"
        "⏱️ `general` has a **10-second slowmode**.\n"
        "🔒 Normal members cannot see the setup yet.\n\n"
        "Run `/showsetup` when you're ready.",
        ephemeral=True
    )


# =========================================================
# /SHOWSETUP
# =========================================================

@tree.command(
    name="showsetup",
    description="Open the SSP verification system"
)
@app_commands.checks.has_permissions(administrator=True)
async def showsetup(interaction: discord.Interaction):
    guild = interaction.guild

    if guild is None:
        await interaction.response.send_message(
            "❌ Use this command inside your server.",
            ephemeral=True
        )
        return

    category = discord.utils.get(
        guild.categories,
        name=CATEGORY_NAME
    )

    if category is None:
        await interaction.response.send_message(
            "❌ Run `/setup` first.",
            ephemeral=True
        )
        return

    everyone = guild.default_role

    rules_channel = discord.utils.get(
        category.text_channels,
        name=RULES_CHANNEL_NAME
    )

    verify_channel = discord.utils.get(
        category.text_channels,
        name=VERIFY_CHANNEL_NAME
    )

    general_channel = discord.utils.get(
        category.text_channels,
        name=GENERAL_CHANNEL_NAME
    )

    verified_role = discord.utils.get(
        guild.roles,
        name=VERIFIED_ROLE_NAME
    )

    await category.set_permissions(
        everyone,
        view_channel=True
    )

    if rules_channel:
        await rules_channel.set_permissions(
            everyone,
            view_channel=True,
            send_messages=False,
            add_reactions=False
        )

    if verify_channel:
        await verify_channel.set_permissions(
            everyone,
            view_channel=True,
            send_messages=False
        )

    if general_channel:
        await general_channel.set_permissions(
            everyone,
            view_channel=False,
            send_messages=False
        )

        if verified_role:
            await general_channel.set_permissions(
                verified_role,
                view_channel=True,
                send_messages=True,
                read_message_history=True
            )

        await general_channel.edit(slowmode_delay=10)

    await interaction.response.send_message(
        "✅ **Verification is open!**\n"
        "Members can see the rules and verification channel.\n"
        "They press **✅ Verify** to unlock `💬・general`.",
        ephemeral=True
    )


# =========================================================
# /HIDESETUP
# =========================================================

@tree.command(
    name="hidesetup",
    description="Hide the SSP verification system"
)
@app_commands.checks.has_permissions(administrator=True)
async def hidesetup(interaction: discord.Interaction):
    guild = interaction.guild

    if guild is None:
        await interaction.response.send_message(
            "❌ Use this command inside your server.",
            ephemeral=True
        )
        return

    category = discord.utils.get(
        guild.categories,
        name=CATEGORY_NAME
    )

    if category is None:
        await interaction.response.send_message(
            "❌ Verification setup not found.",
            ephemeral=True
        )
        return

    everyone = guild.default_role

    await category.set_permissions(
        everyone,
        view_channel=False
    )

    for channel in category.channels:
        await channel.set_permissions(
            everyone,
            view_channel=False
        )

    await interaction.response.send_message(
        "🙈 Verification system is hidden.",
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
    member="Member to remove verification from"
)
@app_commands.checks.has_permissions(administrator=True)
async def unverify(
    interaction: discord.Interaction,
    member: discord.Member
):
    guild = interaction.guild

    if guild is None:
        await interaction.response.send_message(
            "❌ Use this command inside your server.",
            ephemeral=True
        )
        return

    verified_role = discord.utils.get(
        guild.roles,
        name=VERIFIED_ROLE_NAME
    )

    if verified_role is None:
        await interaction.response.send_message(
            "❌ Verified role not found.",
            ephemeral=True
        )
        return

    if verified_role not in member.roles:
        await interaction.response.send_message(
            f"⚠️ {member.mention} is not verified.",
            ephemeral=True
        )
        return

    try:
        await member.remove_roles(
            verified_role,
            reason=f"Removed by {interaction.user}"
        )

        await interaction.response.send_message(
            f"✅ Removed verification from {member.mention}.",
            ephemeral=True
        )

    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ I can't remove the role.\n"
            "Move my bot role above `Verified` and make sure I have **Manage Roles**.",
            ephemeral=True
        )


# =========================================================
# ERROR HANDLER
# =========================================================

@tree.error
async def on_app_command_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError
):
    print("")
    print("==========================================")
    print("❌ COMMAND ERROR")
    print("==========================================")
    print(repr(error))

    if hasattr(error, "original"):
        print("ORIGINAL ERROR:")
        print(repr(error.original))

    print("==========================================")
    print("")

    if isinstance(error, app_commands.MissingPermissions):
        message = "❌ You need Administrator permission to use this command."
    else:
        message = "❌ Something went wrong. Check the bot logs for the exact error."

    try:
        if interaction.response.is_done():
            await interaction.followup.send(
                message,
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                message,
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
            "DISCORD_BOT_TOKEN is missing. "
            "Add it as an environment variable in Railway."
        )

    client.run(TOKEN)
