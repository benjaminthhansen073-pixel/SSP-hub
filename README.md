# SSP Modding Hub Bot

Discord verification bot for SSP Modding Hub.

## Railway setup

1. Upload these files to a GitHub repository.
2. Create a Railway project from the GitHub repository.
3. In Railway, add a variable named:

   DISCORD_BOT_TOKEN

4. Put your NEW Discord bot token in that variable.
5. Deploy the service.

Do NOT paste your Discord bot token into bot.py or GitHub.

## Discord permissions

The bot should have:
- View Channels
- Send Messages
- Embed Links
- Read Message History
- Manage Channels
- Manage Roles

The bot's role must be above the `Verified` role.

## Commands

- `/ping`
- `/setup`
- `/showsetup`
- `/hidesetup`
- `/unverify`

`/setup` creates the verification channels and a `Verified` role.
`/showsetup` opens verification to members.
Pressing the Verify button gives the member the `Verified` role.
`💬・general` uses a 10-second slowmode.
