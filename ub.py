import os
import json
import asyncio
import random
import sys
import logging
import random
import time
import coloredlogs
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError
from datetime import datetime

# Load environment variables
load_dotenv()
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
PHONE = os.getenv("PHONE")
DELAY_MIN = 30
DELAY_MAX = 60
BREAK_DELAY = 10800  # 3 hours

GROUPS_FILE = "groups.json"
MESSAGES_FILE = "messages.json"

# For uptime tracking
START_TIME = time.time()

# Ensure the 'logs/' directory exists
log_dir = os.path.join(os.path.dirname(__file__), "logs")
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# Configure Logging without Colors
log_format = "%(asctime)s - %(message)s"
logging.basicConfig(
    level=logging.INFO,
    format=log_format,
    handlers=[
        logging.FileHandler(os.path.join(log_dir, "app.log")),
        logging.StreamHandler()
    ],
)

# Helper Function to Log Events with Format
def log_event(event_type, details=None, group_name=None, group_id=None):
    if event_type == "MSG":
        message = f"[MSG] - Pesan dikirimkan ke {group_name} - {group_id}"
    elif event_type == "FWD":
        message = f"[FWD] - Pesan diteruskan ke {group_name} - {group_id}"
    elif event_type == "DELAY":
        message = f"[DELAY] - Pesan dijeda selama {details} detik"
    elif event_type == "BREAK":
        message = f"[BREAK] - Pesan ditunda selama {details} jam hingga pengiriman selanjutnya"
    else:
        message = f"[UNKNOWN] - {details}"

    logging.info(message)

# Contoh penggunaan fungsi log_event
log_event("MSG", None, group_name="My Group", group_id=12345)
log_event("FWD", None, group_name="My Group", group_id=12345)
log_event("DELAY", "30")
log_event("BREAK", "2")

# Logging helper function
def log_action(action, details, status="INFO"):
    """Log actions with colored tags."""
    colors = {"INFO": "\033[94m", "SUCCESS": "\033[92m", "ERROR": "\033[91m"}
    color = colors.get(status, "\033[94m")
    header = f"{color}[{status} - USERBOT]\033[0m - {time.strftime('%Y-%m-%d %H:%M:%S')} - {action}"
    print(f"{header} - {details}")

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
    """Load groups and messages from JSON files."""
    global group_ids, messages
    if os.path.exists(GROUPS_FILE):
        with open(GROUPS_FILE, "r") as f:
            data = json.load(f)
            # Konversi elemen `id` saja ke format lengkap
            group_ids = [
                {"id": group["id"], "name": group.get("name", f"Unknown Group {group['id']}")}
                if isinstance(group, dict)
                else {"id": group, "name": f"Unknown Group {group}"}
                for group in data
            ]
    if os.path.exists(MESSAGES_FILE):
        with open(MESSAGES_FILE, "r") as f:
            messages = json.load(f)

def save_data():
    """Save groups and messages to JSON files."""
    with open(GROUPS_FILE, "w") as f:
        json.dump(group_ids, f, indent=4)  # Save with indentation for readability
    with open(MESSAGES_FILE, "w") as f:
        json.dump(messages, f, indent=4)

# Load whitelist from file (optional)
WHITELIST_FILE = "whitelist.json"
if os.path.exists(WHITELIST_FILE):
    with open(WHITELIST_FILE, "r") as f:
        whitelist_groups = json.load(f)

def save_whitelist():
    """Save whitelist groups to JSON file."""
    global whitelist_groups
    with open(WHITELIST_FILE, "w") as f:
        json.dump(whitelist_groups, f, indent=4)

if os.path.exists(WHITELIST_FILE):
    with open(WHITELIST_FILE, "r") as f:
        whitelist_groups = json.load(f)

# Fungsi Utility: parse_indices
def parse_indices(indices):
    """Parse a string of indices (e.g., "1,3-5") into a list of integers."""
    result = []
    parts = indices.split(",")
    for part in parts:
        if "-" in part:
            start, end = map(int, part.split("-"))
            result.extend(range(start, end + 1))
        else:
            result.append(int(part))
    return sorted(set(result))

# Set Break Delay
def jeda_sesi (hours):
    """Set break delay by converting hours to seconds."""
    global BREAK_DELAY
    try:
        BREAK_DELAY = int(hours) * 3600
        log_action("BREAK DELAY UPDATED", f"New Break Delay: {BREAK_DELAY} seconds", "SUCCESS")
        return f"Break delay updated successfully to {hours} hour(s) ({BREAK_DELAY} seconds)."
    except ValueError:
        log_action("INVALID INPUT", "Failed to update break delay.", "ERROR")
        return "Error: Please enter a valid number for hours."

# View Bot Status
def get_uptime():
    """Calculate the bot's uptime."""
    uptime_seconds = int(time.time() - START_TIME)
    hours, remainder = divmod(uptime_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}h {minutes}m {seconds}s"

def get_status():
    """Get bot status (online) and uptime."""
    status = "ONLINE"
    uptime = get_uptime()
    log_action("STATUS CHECK", f"Status: {status}, Uptime: {uptime}", "INFO")
    return f"Userbot is currently {status}.\nUptime: {uptime}."


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
    log_event(f"Using selected message: {selected_message}")
    while True:
        log_event("Starting a new sending session...")
        for group_id in group_ids:
            try:
                log_event(f"Sending to group {group_id}: {selected_message}")
                peer = await client.get_entity(group_id['id']) 
                await client.send_message(peer, selected_message, parse_mode='HTML')
                log_event("MSG", None, group_name=group_id['name'], group_id=group_id['id'])
            except Exception as e:
                log_event("Error sending message", group_id['name'], str(e))
            delay = random.randint(DELAY_MIN, DELAY_MAX)
            log_event("DELAY", delay)
            await asyncio.sleep(delay)
        log_event("BREAK", BREAK_DELAY // 3600)  # Jam
        await asyncio.sleep(BREAK_DELAY)

async def forward_message_once(reply_message):
    """Forward a message once to all groups."""
    for group_id in group_ids:
        try:
            peer = await client.get_entity(group_id['id'])
            await client.forward_messages(peer, reply_message)
            log_event("FWD", None, group_name=group_id['name'], group_id=group_id['id'])
        except Exception as e:
            log_event("Error forwarding message", group_id['name'], str(e))
        delay = random.randint(DELAY_MIN, DELAY_MAX)
        log_event("DELAY", delay)
        await asyncio.sleep(delay)

async def auto_forward_message(reply_message):
    """Continuously forward a message with delay."""
    while True:
        log_event("Starting auto-forward session...")
        for group_id in group_ids:
            try:
                peer = await client.get_entity(group_id['id'])
                await client.forward_messages(peer, reply_message)
                log_event("FWD", None, group_name=group_id['name'], group_id=group_id['id'])
            except Exception as e:
                log_event(f"Failed to forward to {group_id}: {e}")
            delay = random.randint(DELAY_MIN, DELAY_MAX)
            log_event("DELAY", delay)
            await asyncio.sleep(delay)
        log_event("BREAK", BREAK_DELAY // 3600)  # Jam
        await asyncio.sleep(BREAK_DELAY)

# Event Handlers
@client.on(events.NewMessage(pattern=r"\.addgroupid (\d+)"))
async def handle_add_group(event):
    group_id = int(event.pattern_match.group(1))
    try:
        # Ambil informasi nama grup berdasarkan ID
        group_entity = await client.get_entity(group_id)
        group_name = group_entity.title

        # Tambahkan grup ke daftar jika belum ada
        if not any(group['id'] == group_id for group in group_ids):
            group_ids.append({"id": group_id, "name": group_name})
            save_data()
            await event.edit(f"Group {group_name} (ID: {group_id}) added.")
            print(f"Group {group_name} (ID: {group_id}) added.")
        else:
            await event.edit("Group ID already exists in the list.")
    except Exception as e:
        await event.edit(f"Failed to add group: {e}")
    print(f"Group ID handled: {group_id}")

@client.on(events.NewMessage(pattern=r"\.addgroup (.+)"))
async def add_group_by_name(event):
    group_name = event.pattern_match.group(1)
    try:
        async for dialog in client.iter_dialogs():
            if dialog.is_group and dialog.title == group_name:
                if not any(group['id'] == dialog.id for group in group_ids):
                    group_ids.append({"id": dialog.id, "name": dialog.title})
                    save_data()
                    await event.edit(f"Group {group_name} (ID: {dialog.id}) added.")
                    print(f"Group {group_name} (ID: {dialog.id}) added.")
                    return
                else:
                    await event.edit("Group already exists in the list.")
                    return
        await event.edit("Group not found.")
    except Exception as e:
        await event.edit(f"Failed to add group: {e}")
    print(f"Group added by name: {group_name}")

@client.on(events.NewMessage(pattern=r"\.hapus ([\d,-]+)"))
async def delete_groups(event):
    """Delete multiple groups by indices."""
    indices = event.pattern_match.group(1)
    try:
        # Parsing input (e.g., "1,3-5" -> [1, 3, 4, 5])
        indices = parse_indices(indices)
        removed_groups = []
        
        for index in sorted(indices, reverse=True):
            if 0 <= index - 1 < len(group_ids):
                removed_groups.append(group_ids.pop(index - 1))
        
        save_data()
        response = "\n".join([f"Removed: {group['name']} (ID: {group['id']})" for group in removed_groups])
        await event.edit(f"Successfully removed the following groups:\n{response}")
    except Exception as e:
        await event.edit(f"Error removing groups: {e}")
    print("Deleted multiple groups.")

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
    """List saved groups with names and IDs from groups.json."""
    if group_ids:
        response = "\n".join([f"{i + 1}. {group['name']} (ID: {group['id']})" for i, group in enumerate(group_ids)])
        await event.edit(f"Groups in list:\n{response}")
    else:
        await event.edit("No groups found in the group list.")
    print("Listed saved group names and IDs.")

@client.on(events.NewMessage(pattern=r"\.grupall"))
async def handle_list_all_groups(event):
    """List all groups and save their names and IDs to groups.json."""
    global group_ids
    group_ids = []  # Clear existing list

    async for dialog in client.iter_dialogs():
        if dialog.is_group:  # Check if it's a group
            group_entry = {"id": dialog.id, "name": dialog.title}
            if group_entry not in group_ids:
                group_ids.append(group_entry)

    # Save updated group list
    save_data()

    if group_ids:
        response = "\n".join([f"{i + 1}. {group['name']} (ID: {group['id']})" for i, group in enumerate(group_ids)])
        await event.edit(f"All Groups (Updated List):\n{response}")
    else:
        await event.edit("No groups found on this account.")
    print("Listed all groups with names.")

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
    
    # Specify the full path for python3 on Ubuntu
    python3_path = "/usr/bin/python3"  # Adjust if necessary

    # Use os.execv to restart the script with the correct Python 3 interpreter
    os.execv(python3_path, [python3_path] + sys.argv)

@client.on(events.NewMessage(pattern=r"\.whitelist ([\d,-]+)"))
async def whitelisting_groups(event):
    """Whitelist multiple groups by indices."""
    indices = event.pattern_match.group(1)
    try:
        indices = parse_indices(indices)
        whitelisted_groups = []
        
        for index in sorted(indices, reverse=True):
            if 0 <= index - 1 < len(group_ids):
                group = group_ids.pop(index - 1)
                if group not in whitelist_groups:
                    whitelist_groups.append(group)
                    whitelisted_groups.append(group)
        
        save_data()
        save_whitelist()
        
        if whitelisted_groups:
            response = "\n".join([f"Whitelisted: {group['name']} (ID: {group['id']})" for group in whitelisted_groups])
            await event.edit(f"Successfully whitelisted the following groups:\n{response}")
        else:
            await event.edit("No groups were whitelisted.")
    except Exception as e:
        await event.edit(f"Error whitelisting groups: {e}")
    print("Whitelisted multiple groups.")

@client.on(events.NewMessage(pattern=r"\.restore ([\d,-]+)"))
async def restore_groups(event):
    """Restore multiple groups by indices from whitelist to main group list."""
    indices = event.pattern_match.group(1)
    try:
        indices = parse_indices(indices)
        restored_groups = []
        
        for index in sorted(indices, reverse=True):
            if 0 <= index - 1 < len(whitelist_groups):
                group = whitelist_groups.pop(index - 1)
                if group not in group_ids:
                    group_ids.append(group)
                    restored_groups.append(group)
        
        save_data()
        save_whitelist()
        
        if restored_groups:
            response = "\n".join([f"Restored: {group['name']} (ID: {group['id']})" for group in restored_groups])
            await event.edit(f"Successfully restored the following groups:\n{response}")
        else:
            await event.edit("No groups were restored.")
    except Exception as e:
        await event.edit(f"Error restoring groups: {e}")
    print("Restored multiple groups.")

@client.on(events.NewMessage(pattern=r"\.whitelistlist"))
async def view_whitelist(event):
    """List all groups in the whitelist."""
    if whitelist_groups:
        response = "\n".join([f"{i + 1}. {group['name']} (ID: {group['id']})" for i, group in enumerate(whitelist_groups)])
        await event.edit(f"Whitelisted Groups:\n{response}")
    else:
        await event.edit("No groups in the whitelist.")
    print("Listed all whitelisted groups.")

@client.on(events.NewMessage(pattern=r"\.jeda_sesi (\d+)"))
async def modify_break_delay(event):
    """Handle setting the break delay."""
    hours = event.pattern_match.group(1)
    response = jeda_sesi(hours)
    await event.edit(response)

@client.on(events.NewMessage(pattern=r"\.status$"))
async def view_status(event):
    """Handle viewing the bot's status."""
    response = get_status()
    await event.edit(response)

@client.on(events.NewMessage(pattern=r"\.daftar"))
async def list_events(event):
    commands = [
        
        "<blockquote>𝙋𝙀𝙍𝙄𝙉𝙏𝘼𝙃 𝘿𝘼𝙎𝘼𝙍</blockquote>\n"
        "<b>Restart bot</b> -> <code>.restart</code>\n"
        "Merestart bot untuk menerapkan perubahan atau mengatasi masalah.",

        "<b>Status</b> -> <code>.status</code>\n"
        "Mengetahui Status terkini dari bot",

        "<blockquote>𝙋𝙀𝙍𝙄𝙉𝙏𝘼𝙃 𝙂𝙍𝙐𝙋</blockquote>\n"
        "<b>Melihat daftar grup</b> -> <code>.grup</code>\n"
        "Menampilkan semua grup yang ada di daftar grup saat ini.",

        "<b>Menambahkan group dengan ID</b> -> <code>.addgroupid <group_id></code>\n"
        "Digunakan untuk menambahkan grup ke dalam daftar grup berdasarkan ID grup.",

        "<b>Menambahkan group dengan nama</b> -> <code>.addgroup <group_name></code>\n"
        "Menambahkan grup ke dalam daftar dengan mencocokkan nama grup di akun Telegram.",

        "<b>Whitelist grup</b> -> <code>.whitelist <nomor></code>\n"
        "Memindahkan grup tertentu dari daftar grup ke daftar whitelist.",

        "<b>Restore grup</b> -> <code>.restore <nomor></code>\n"
        "Mengembalikan grup dari whitelist ke daftar grup utama.",

        "<b>Melihat whitelist grup</b> -> <code>.whitelistlist</code>\n"
        "Melihat isi whitelist.",

        "<b>Menghapus grup berdasarkan nomor urut</b> -> <code>.hapus <nomor></code>\n"
        "Menghapus grup dari daftar berdasarkan urutan dalam daftar grup.",

        "<blockquote>𝙋𝙀𝙍𝙄𝙉𝙏𝘼𝙃 𝙋𝙀𝙎𝘼𝙉</blockquote>\n"
        "<b>Menambahkan pesan baru</b> -> <code>.tambahpesan</code> (reply pesan)\n"
        "Menambahkan pesan baru ke dalam daftar pesan. Gunakan perintah ini dengan me-reply pesan yang ingin ditambahkan.",

        "<b>Melihat daftar pesan</b> -> <code>.pesan</code>\n"
        "Menampilkan semua pesan yang tersimpan di daftar pesan.",

        "<b>Memilih pesan untuk dikirim</b> -> <code>.selectmessage <nomor></code>\n"
        "Memilih pesan berdasarkan nomor urut di daftar pesan untuk digunakan saat pengiriman otomatis.",

        "<blockquote>𝙋𝙀𝙉𝙂𝙄𝙍𝙄𝙈𝘼𝙉 𝙋𝙀𝙎𝘼𝙉</blockquote>\n"
        "<b>Memulai pengiriman pesan otomatis</b> -> <code>.start</code>\n"
        "Memulai pengiriman pesan otomatis ke grup yang ada di daftar grup.",

        "<b>Menghentikan pengiriman pesan otomatis</b> -> <code>.stop</code>\n"
        "Menghentikan proses pengiriman pesan otomatis yang sedang berjalan.",

        "<b>Forward satu kali</b> -> <code>.forwardonce</code> (reply pesan)\n"
        "Memforward pesan ke semua grup di daftar grup sekali saja. Gunakan dengan me-reply pesan yang ingin diforward.",

        "<b>Forward otomatis</b> -> <code>.autoforward</code> (reply pesan)\n"
        "Memulai forward pesan otomatis ke semua grup di daftar grup. Gunakan dengan me-reply pesan yang ingin diforward.",

        "<b>Menghentikan forward otomatis</b> -> <code>.stopforward</code>\n"
        "Menghentikan forward pesan otomatis yang sedang berjalan.",

        "<b>Set Break Time</b> -> <code>.jeda_sesi</code>\n"
        "Mengatur jeda <i>break time</i>"
    ]

    response = """
█▀▀ █▀█ █▀▄▀█ █▀▄▀█ ▄▀█ █▄░█ █▀▄
█▄▄ █▄█ █░▀░█ █░▀░█ █▀█ █░▀█ █▄▀ \n\n""" + "\n\n".join(commands)
    await event.edit(response, parse_mode="html")

    
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
    print("""
██╗   ██╗███████╗███████╗██████╗ ██████╗  ██████╗ ████████╗
██║   ██║██╔════╝██╔════╝██╔══██╗██╔══██╗██╔═══██╗╚══██╔══╝
██║   ██║███████╗█████╗  ██████╔╝██████╔╝██║   ██║   ██║   
██║   ██║╚════██║██╔══╝  ██╔══██╗██╔══██╗██║   ██║   ██║   
╚██████╔╝███████║███████╗██║  ██║██████╔╝╚██████╔╝   ██║   
 ╚═════╝ ╚══════╝╚══════╝╚═╝  ╚═╝╚═════╝  ╚═════╝    ╚═╝   
                                                           """)
    print("Created By: https://t.me/laksitoadi02")
    
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
