import sqlite3

# Connect to your bot's database
conn = sqlite3.connect("./referral_bot.db")
cursor = conn.cursor()

# Fetch all user IDs
cursor.execute("SELECT user_id FROM users")
user_ids = cursor.fetchall()

# Save to file
with open("user_ids.txt", "w") as f:
    for (uid,) in user_ids:
        f.write(f"{uid}\n")

conn.close()
print(f"Exported {len(user_ids)} user IDs to user_ids.txt")
