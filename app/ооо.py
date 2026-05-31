import sqlite3
db = sqlite3.connect("bot_database.db")



vk_id = 1090047591
db.execute("UPDATE users SET onboarding_done = 0 WHERE vk_id = ?", (vk_id,))
db.commit()
print("Готово")