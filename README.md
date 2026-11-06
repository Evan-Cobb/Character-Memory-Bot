# Character Memory Bot

A small Discord bot for practicing data structures: create characters, save memories, undo the last memory change, and process queued memory additions in FIFO order.

The project is appropriate for CSE212-level study. It uses lists, a stack, a map, sets, a custom linked queue, and an unbalanced binary search tree. See the [CSE212 project explanation](docs/CSE212_PLAN.md).

## 1. Install and verify locally

Use Python 3.11 or later. In PowerShell:

```powershell
git clone https://github.com/Evan-Cobb/Character-Memory-Bot.git
Set-Location Character-Memory-Bot
if (-not (Test-Path ".venv\Scripts\python.exe")) { py -3 -m venv .venv }
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe bot.py --check
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

If you already have the project, open PowerShell in its folder and skip the clone. Activation is not necessary when using the explicit executable.

The check should report **9 commands** and a successful create/filter/tree/FIFO/undo/isolation/save-reload exercise. It uses temporary storage, needs no token, does not contact Discord, and does not change your saved characters.

## 2. Configure Discord once

1. Open the [Discord Developer Portal](https://discord.com/developers/applications), select your application (or create one), and open its **Bot** page.
2. Obtain the **bot token**, not the application's client secret. Enable **Message Content Intent** under Privileged Gateway Intents. The code already requests that intent for prefix commands.
3. Under **OAuth2 → URL Generator**, select `bot` and `applications.commands`. Allow **View Channels** and **Send Messages**. Open the generated URL and add the bot to your test server.
4. In Discord, enable Developer Mode under User Settings → Advanced. Right-click the test server and choose **Copy Server ID**.
5. Create your private configuration file without overwriting an existing one:

```powershell
if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env" }
notepad .env
```

Fill in these values and save:

```dotenv
DISCORD_TOKEN=
DISCORD_GUILD_ID=
BOT_DATA_PATH=data/characters.json
```

Set `DISCORD_TOKEN` to your bot token and `DISCORD_GUILD_ID` to your test server ID. Keep the token local. Leaving the server ID blank registers commands globally instead; Discord controls propagation. The private configuration, saved characters, and virtual environment are excluded from Git.

Setup references: [bot account and invitation](https://discordpy.readthedocs.io/en/stable/discord.html), [required gateway intent](https://discordpy.readthedocs.io/en/stable/intents.html).

## 3. Start the bot

From the same project folder:

```powershell
.\.venv\Scripts\python.exe bot.py
```

Wait for **Registered 9 slash commands** and **Connected as ...**. Keep the terminal running. Press **Ctrl+C** to stop. You do not need to run any other Python file or start a web server.

## 4. Try it in Discord

Use these messages in a channel where the bot can send messages. These exact forms are tested through discord.py's argument parser:

```text
!create_character "Ada Lovelace" "Curious and thoughtful" "science,kind"
!enqueue "Ada Lovelace" "First queued fact"
!next
!remember "Ada Lovelace" "Second direct fact"
!undo
!character_info "Ada Lovelace"
!characters science
!help
```

The final info should contain **First queued fact**, not **Second direct fact**. `!undo` reverses the latest memory addition; `!next` saves the oldest queued fact.

The same nine commands are slash commands. In Discord's slash UI, supply the named fields shown below:

| Command | Fields | Behavior |
|---|---|---|
| `/help` | none | List commands |
| `/create_character` | name, personality, optional tags | Create your character; tags are comma-separated |
| `/delete_character` | name | Permanently delete your character and its session data |
| `/character_info` | name | Show profile and five latest memories |
| `/characters` | optional tag | Browse your characters alphabetically |
| `/remember` | name, fact | Save a memory immediately |
| `/undo` | none | Undo your last memory addition this session |
| `/enqueue` | name, fact | Queue a memory addition without saving it yet |
| `/next` | optional discard (default false) | Save the oldest queued memory, or explicitly discard it |

Slash replies are private to the invoking user; prefix replies are visible in the channel. Quote multiword prefix arguments. Each user has separate data per server, and DMs use a separate workspace.

## Data and limits

Profiles, tags, and memories are saved to `data/characters.json`. Existing saved character files remain compatible. Queued additions and undo records are session-local and reset when the bot stops.

Limits per user/server: 100 characters, 100 memories per character, 50 pending additions, and 100 retained undo records. A character supports up to 10 unique normalized tags. Invalid names, duplicates, full/empty structures, and failed saves produce explanatory errors. If `/next` cannot add or save a memory, its queue item remains available for retry. To discard a blocked or unwanted head item, use `/next discard:true` or `!next true`; later queued additions remain intact.

Use one local bot process. JSON saves are synchronous and rewrite the saved data file; this is intentionally a small project, not a multi-process hosting platform. Failed writes are rolled back. A reply can fail after a successful write, so check character state before retrying.

## CSE212

Read the [CSE212 project explanation](docs/CSE212_PLAN.md) for the design choices, data structures, and performance reasoning. The project currently has 51 passing automated tests.

## Troubleshooting

| Symptom | What to check |
|---|---|
| `Set DISCORD_TOKEN` | Save an actual token in `.env` in this folder |
| `Discord rejected DISCORD_TOKEN` | Use the bot token, not the client secret |
| `PrivilegedIntentsRequired` | Enable Message Content Intent on the portal's Bot page |
| Server access/sync error | Check the server ID and that this bot was invited there |
| Slash commands missing | Check the application-command invite scope and test server ID; old commands in another registration scope may remain |
| Prefix commands silent | Check Message Content Intent and the channel's View/Send permissions |
| Import/module error | Install requirements using this folder's `.venv\Scripts\python.exe` |
| Invalid saved data | Preserve the file; correct the malformed data or select a new data path rather than deleting your only copy |
