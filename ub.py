import os
import json
import asyncio
import random
import sys
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError

# Load environment variables
load_dotenv()
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
PHONE = os.getenv("PHONE")
DELAY_MIN = 30
DELAY_MAX = 60
BREAK_DELAY = 7200  # 2 hours

GROUPS_FILE = "groups.json"
MESSAGES_FILE = "messages.json"

client = TelegramClient("userbot_session", API_ID, API_HASH)

# Load group IDs and messages
group_ids = []
messages = []
whitelist_groups = []

selected_message_index = 0
task = None
forward_task = None

# Load groups and messages from files
def load_data():
    global group_ids, messages
    if os.path.exists(GROUPS_FILE):
        with open(GROUPS_FILE, "r") as f:
            group_ids = json.load(f)
    if os.path.exists(MESSAGES_FILE):
        with open(MESSAGES_FILE, "r") as f:
            messages = json.load(f)

def save_data():
    with open(GROUPS_FILE, "w") as f:
        json.dump(group_ids, f)
    with open(MESSAGES_FILE, "w") as f:
        json.dump(messages, f)

# Load whitelist from file (optional)
WHITELIST_FILE = "whitelist.json"
if os.path.exists(WHITELIST_FILE):
    with open(WHITELIST_FILE, "r") as f:
        whitelist_groups = json.load(f)

def save_whitelist():
    with open(WHITELIST_FILE, "w") as f:
        json.dump(whitelist_groups, f)

# Initialize data
load_data()

# Helper Functions
async def send_messages():
    """Send the selected message to all group IDs with delay."""
    if not messages:
        return "No messages to send. Add a message first."
    if not group_ids:
        return "No group IDs available. Add a group first."

    selected_message = messages[selected_message_index]
    print(f"Using selected message: {selected_message}")
    while True:
        print("Starting a new sending session...")
        for group_id in group_ids:
            try:
                print(f"Sending to group {group_id}: {selected_message}")
                peer = await client.get_entity(group_id)
                await client.send_message(peer, selected_message, parse_mode='HTML')
            except Exception as e:
                print(f"Failed to send message to {group_id}: {e}")
            delay = random.randint(DELAY_MIN, DELAY_MAX)
            print(f"Waiting {delay} seconds before sending the next message...")
            await asyncio.sleep(delay)
        print(f"Session complete. Waiting {BREAK_DELAY // 60} minutes before the next session...")
        await asyncio.sleep(BREAK_DELAY)

async def forward_message_once(reply_message):
    """Forward a message once to all groups."""
    for group_id in group_ids:
        try:
            peer = await client.get_entity(group_id)
            await client.forward_messages(peer, reply_message)
            print(f"Forwarded to {group_id}")
        except Exception as e:
            print(f"Failed to forward to {group_id}: {e}")
        delay = random.randint(DELAY_MIN, DELAY_MAX)
        await asyncio.sleep(delay)

async def auto_forward_message(reply_message):
    """Continuously forward a message with delay."""
    while True:
        print("Starting auto-forward session...")
        for group_id in group_ids:
            try:
                peer = await client.get_entity(group_id)
                await client.forward_messages(peer, reply_message)
                print(f"Forwarded to {group_id}")
            except Exception as e:
                print(f"Failed to forward to {group_id}: {e}")
            delay = random.randint(DELAY_MIN, DELAY_MAX)
            print(f"Waiting {delay} seconds before sending the next message...")
            await asyncio.sleep(delay)
        print(f"Auto-forward session complete. Waiting {BREAK_DELAY // 60} minutes before next session...")
        await asyncio.sleep(BREAK_DELAY)

# Event Handlers
@client.on(events.NewMessage(pattern=r"\.addgroupid (\d+)"))
async def handle_add_group(event):
    group_id = int(event.pattern_match.group(1))
    if group_id not in group_ids:
        group_ids.append(group_id)
        save_data()
        await event.edit(f"Group ID {group_id} added.")
    else:
        await event.edit("Group ID already exists.")
    print(f"Group ID handled: {group_id}")

@client.on(events.NewMessage(pattern=r"\.addgroup (.+)"))
async def add_group_by_name(event):
    group_name = event.pattern_match.group(1)
    async for dialog in client.iter_dialogs():
        if dialog.is_group and dialog.title == group_name:
            if dialog.id not in group_ids:
                group_ids.append(dialog.id)
                save_data()
                await event.edit(f"Group {group_name} (ID: {dialog.id}) added.")
                print(f"Group {group_name} (ID: {dialog.id}) added.")
                return
            else:
                await event.edit("Group already exists in the list.")
                return
    await event.edit("Group not found.")

@client.on(events.NewMessage(pattern=r"\.hapus (\d+)"))
async def delete_group(event):
    index = int(event.pattern_match.group(1)) - 1
    if 0 <= index < len(group_ids):
        removed_group = group_ids.pop(index)
        save_data()
        await event.edit(f"Group ID {removed_group} removed.")
        print(f"Group ID {removed_group} removed.")
    else:
        await event.edit("Invalid group index.")

@client.on(events.NewMessage(pattern=r"\.tambahpesan"))
async def handle_add_message(event):
    if event.reply_to_msg_id:
        reply = await event.get_reply_message()
        message = reply.text
        if message:
            messages.append(message)
            save_data()
            await event.edit("Message added successfully.")
            print(f"Message added: {message}")
        else:
            await event.edit("Replied message is empty or not text.")
    else:
        await event.edit("Reply to a message to add it.")

@client.on(events.NewMessage(pattern=r"\.grup"))
async def handle_list_group_ids(event):
    if group_ids:
        # Ambil semua dialog dan filter hanya grup yang ada di group_ids
        dialogs = await client.get_dialogs()
        response = "\n".join([f"{i + 1}. {dialog.title} (ID: {dialog.id})" for i, dialog in enumerate(dialogs) if dialog.is_group and dialog.id in group_ids])
        await event.edit(f"Group IDs (List):\n{response}")
    else:
        await event.edit("No groups found in the group list.")
    print("Listed group IDs.")

@client.on(events.NewMessage(pattern=r"\.grupall"))
async def handle_list_all_groups(event):
    global group_ids
    group_ids = []  # Clear the existing list

    # Fetch all dialogs and filter only group chats
    async for dialog in client.iter_dialogs():
        if dialog.is_group:  # Check if the dialog is a group
            group_ids.append(dialog.id)

    # Save updated group list
    save_data()

    if group_ids:
        # Ambil semua dialog dan filter hanya grup
        dialogs = await client.get_dialogs()
        response = "\n".join([f"{i + 1}. {dialog.title} (ID: {dialog.id})" for i, dialog in enumerate(dialogs) if dialog.is_group])
        await event.edit(f"All Groups (Updated List):\n{response}")
    else:
        await event.edit("No groups found on this account.")
    print("Listed all groups.")

@client.on(events.NewMessage(pattern=r"\.pesan"))
async def handle_list_messages(event):
    if messages:
        response = "\n\n".join([f"**{i + 1}.** {msg}" for i, msg in enumerate(messages)])
        await event.edit(f"Messages:\n\n{response}")
    else:
        await event.edit("No messages available.")
    print("Listed messages.")

@client.on(events.NewMessage(pattern=r"\.selectmessage (\d+)"))
async def handle_select_message(event):
    global selected_message_index
    index = int(event.pattern_match.group(1)) - 1
    if 0 <= index < len(messages):
        selected_message_index = index
        await event.edit(f"Message #{index + 1} selected: {messages[index]}")
    else:
        await event.edit("Invalid message index.")
    print(f"Selected message index: {index}")

@client.on(events.NewMessage(pattern=r"\.start"))
async def start_sending(event):
    global task
    if task and not task.done():
        await event.edit("Message sending is already in progress.")
    else:
        task = asyncio.create_task(send_messages())
        await event.edit("Started sending messages.")
    print("Started message sending.")

@client.on(events.NewMessage(pattern=r"\.stop"))
async def stop_sending(event):
    global task
    if task and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            print("Message sending stopped by user.")
        task = None
        await event.edit("Message sending process stopped and logged.")
    else:
        await event.edit("No active message-sending process.")
    print("Stopped message sending.")

@client.on(events.NewMessage(pattern=r"\.forwardonce"))
async def handle_forward_once(event):
    if event.reply_to_msg_id:
        reply_message = await event.get_reply_message()
        await forward_message_once(reply_message)
        await event.edit("Message forwarded once to all groups.")
    else:
        await event.edit("Reply to a message to forward it.")

@client.on(events.NewMessage(pattern=r"\.autoforward"))
async def handle_auto_forward(event):
    global forward_task
    if forward_task and not forward_task.done():
        await event.edit("Auto-forwarding is already in progress.")
    else:
        if event.reply_to_msg_id:
            reply_message = await event.get_reply_message()
            forward_task = asyncio.create_task(auto_forward_message(reply_message))
            await event.edit("Started auto-forwarding.")
        else:
            await event.edit("Reply to a message to auto-forward it.")

@client.on(events.NewMessage(pattern=r"\.stopforward"))
async def stop_auto_forward(event):
    global forward_task
    if forward_task and not forward_task.done():
        forward_task.cancel()
        try:
            await forward_task
        except asyncio.CancelledError:
            print("Auto-forwarding stopped by user.")
        forward_task = None
        await event.edit("Auto-forwarding process stopped.")
    else:
        await event.edit("No active auto-forwarding process.")

@client.on(events.NewMessage(pattern=r"\.restart"))
async def restart_bot(event):
    await event.edit("Restarting bot...")
    print("Restarting bot...")
    # Log restart to a file
    with open("restart_log.txt", "a") as log_file:
        log_file.write("Restarting bot...\n")
    print(f"Python executable: {sys.executable}")
    if not os.path.exists(sys.executable):
        await event.edit(f"Python executable not found: {sys.executable}")
        return
    os.execv(sys.executable, ['python'] + sys.argv)
    
# Main Function
async def main():
    if not await client.is_user_authorized():
        await client.send_code_request(PHONE)
        try:
            code = input("Enter the code you received: ")
            await client.sign_in(PHONE, code)
        except SessionPasswordNeededError:
            password = input("Enter your 2FA password: ")
            await client.sign_in(password=password)
    print("Logged in successfully.")
    
    # Dapatkan ID pengguna Anda
    me = await client.get_me()
    user_id = me.id
    
    # Kirim pesan log ke Saved Messages setelah restart
    await client.send_message(user_id, "Restart berhasil.")
    
    await client.run_until_disconnected()

# Run the client
if __name__ == "__main__":
    client.start()
    client.loop.run_until_complete(main())