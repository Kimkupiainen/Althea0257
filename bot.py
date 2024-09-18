import os
import asyncio
import discord
from discord.ext import commands
from datetime import datetime

TOKEN = os.getenv('DISCORD_BOT_TOKEN')
# Define intents
intents = discord.Intents.default()
intents.messages = True  # Enables listening for messages
intents.message_content = True
intents.guilds = True    # Enables interaction with servers (guilds)

# Bot command prefix (e.g., !)
bot = commands.Bot(command_prefix='!', intents=intents)

#Bot responses
MSG_NO_ACTIVE_THREAD = "You have no active report thread."
MSG_REPORT_CLOSED = "Your report has been closed. Thank you for reaching out."
MSG_REPORT_ERROR = "Error: Cannot find the specified report channel."
MSG_HOWTO = ("\nAlthea is an Anti-harassment bot designed to keep you anonymous until you feel safe enough "
             "to tell more details about yourself!\n!report to start a discussion anonymously.\n"
             "When you are ready to reveal your identity, use the command !reveal.")
MSG_REPORT_STARTED = "A thread has been created for your report in the report channel. You are currently anonymous. You can now send messages that will be forwarded anonymously.\nType !stop to end the report or !reveal to share your identity. \nRemember that the most important thing is to be DESCRIPTIVE of WHAT happened, WHERE, and WHO were involved. \nThis is for the safety of our whole community. \nIf you have proof ie. Images, feel free to share those as they will solidify the case you're making."
MSG_REVEAL_IDENTITY = "Your Discord identity has been revealed to the anti-harassment team."
MSG_NO_ACTIVE_REPORT = "It seems you don't have an active report. Here are some available commands:\n" \
                       "- `!report` - Start a new anonymous report\n" \
                       "- `!howto` - Get instructions on how to use the bot\n" \
                       "- `!stop` - End an active report if it exists\n" \
                       "- `!reveal` - Reveal your identity to the anti-harassment team."
# Dictionary to keep track of threads and users
active_threads = {}
anonymous_users = {}
help_message_sent = {}

# Channel ID where all threads will be created
REPORT_CHANNEL_ID = 1234567 # Example channel ID, needs to be replaced with the actual channel

# Role ID for moderators (replace this with your actual moderator role ID)
MODERATOR_ROLE_ID = 1234567  # Example role ID, replace with actual moderator role

# Bot is ready
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')

# Simple command to explain bot usage
@bot.command()
@commands.cooldown(rate=2, per=30.0, type=commands.BucketType.user)  # Limit to 2 uses per 30 seconds per user
async def howto(ctx):
    await ctx.send(MSG_HOWTO + '\n' + MSG_NO_ACTIVE_REPORT)

# Command to start a report (create a thread in the specific channel)
@bot.command()
@commands.cooldown(rate=1, per=60.0, type=commands.BucketType.user)  # Limit to 1 use per minute per user
async def report(ctx):
    # Fetch the report channel by ID
    report_channel = bot.get_channel(REPORT_CHANNEL_ID)
    
    if report_channel is None:
        await ctx.send(MSG_REPORT_ERROR)
        return
    
    # Create a thread in the report channel
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    thread = await report_channel.create_thread(
        name=f"Anonymous Report at {current_time}",
        type=discord.ChannelType.public_thread  # You can change this to private_thread if needed
    )
    
    # Store the thread so we can forward messages later
    active_threads[ctx.author.id] = thread
    
    # Assign the user an anonymous label (e.g., Reporter #)
    anonymous_label = f"Reporter #{len(anonymous_users) + 1}"
    anonymous_users[ctx.author.id] = anonymous_label
    
    await ctx.send(MSG_REPORT_STARTED + ' \nYou are now communicating as ' + anonymous_label)

# Command to stop forwarding messages and close the thread
@bot.command()
@commands.cooldown(rate=1, per=300.0, type=commands.BucketType.user)  # Limit to 1 use per 5 minutes per user
async def stop(ctx):
    if ctx.author.id in active_threads:
        thread = active_threads[ctx.author.id]
        await thread.send("The reporting conversation has been ended.")
        await ctx.send(MSG_REPORT_CLOSED)
        await thread.edit(archived=True)  # Archive the thread when stopping
        del active_threads[ctx.author.id]  # Remove the user from active threads
        anonymous_users.pop(ctx.author.id, None)
        help_message_sent.pop(ctx.author.id, None)
    else:
        await ctx.send(MSG_NO_ACTIVE_REPORT)

# Command to reveal the user's identity to the thread
@bot.command()
async def reveal(ctx):
    if ctx.author.id in active_threads:
        thread = active_threads[ctx.author.id]
        await thread.send(f'{ctx.author.global_name} - {ctx.author.id} \nHas revealed their identity.{ctx.author.avatar}')
        await ctx.send(f'Your discord identity has been revealed to the anti-harassment team. based on your commands')
        # Remove the user from anonymous list
        del anonymous_users[ctx.author.id]
    else:
        await ctx.send(MSG_NO_ACTIVE_REPORT)

# Forward messages from the reporter's DM to the thread
@bot.event
async def on_message(message):
    # Check if the message is a DM to the bot (from the user/reporter)
    if isinstance(message.channel, discord.DMChannel):
        if message.author.id in active_threads:
            thread = active_threads[message.author.id]
            # Construct the content to forward
            content_to_forward = message.content

            # Check if there are attachments
            if message.attachments:
                attachment_links = [attachment.url for attachment in message.attachments]
                content_to_forward += "\n\nAttachments:\n" + "\n".join(attachment_links)
            
            # Check if the thread is still valid
            if thread and thread.guild:  # Ensure the thread is still in a valid guild
                try:
                    if message.author.id in anonymous_users:
                        anonymous_label = anonymous_users[message.author.id]
                        await thread.send(f'{anonymous_label}: {content_to_forward}')  # Forward message anonymously
                    else:
                        await thread.send(f'{message.author.name}: {content_to_forward}')  # If they revealed, use their real name
                except discord.errors.NotFound:
                    del active_threads[message.author.id]  # Clean up if thread is gone
            else:
                del active_threads[message.author.id]  # Clean up if thread is gone
        else:
            if not help_message_sent.get(message.author.id, False):
                help_message_sent[message.author.id] = True
                await message.channel.send(
                 "It seems you don't have an active report. Here are some available commands:\n"
                    "- `!report` - Start a new anonymous report\n"
                    "- `!howto` - Get instructions on how to use the bot\n"
                    "- `!stop` - End an active report if it exists\n"
                    "- `!reveal` - Reveal your identity to the anti-harassment team")
                await asyncio.sleep(2)
                return
    
    # Check if the message is in a thread
    elif isinstance(message.channel, discord.Thread):
        # Find the corresponding user for the thread
        for user_id, thread in active_threads.items():
            if message.channel.id == thread.id:
                # First, check if the message is from a moderator and forward it to the user
                if any(role.id == MODERATOR_ROLE_ID for role in message.author.roles):
                    user = await bot.fetch_user(user_id)
                    if user.dm_channel is None:
                        await user.create_dm()
                    await user.dm_channel.send(f'Anti-harassment personnel: {message.content}')
                break
    
    # Process bot commands
    await bot.process_commands(message)

if TOKEN:
    bot.run(TOKEN)
else:  
    print('token not found')
