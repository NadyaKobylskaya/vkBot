import sqlite3

con = sqlite3.connect(r'C:\MY\VK_BOT2.0\app\bot_database.db')

rows = con.execute('''
    SELECT u.vk_id, u.username, u.last_active,
           COUNT(a.id) as total,
           SUM(CASE WHEN a.is_correct = 1 THEN 1 ELSE 0 END) as correct,
           SUM(CASE WHEN t.exam_type = 'oge'         THEN 1 ELSE 0 END) as oge,
           SUM(CASE WHEN t.exam_type = 'ege_profile' THEN 1 ELSE 0 END) as egep,
           SUM(CASE WHEN t.exam_type = 'ege_base'    THEN 1 ELSE 0 END) as egeb
    FROM users u
    LEFT JOIN attempts a ON a.user_id = u.id
    LEFT JOIN tasks t    ON t.id = a.task_id
    GROUP BY u.vk_id
    ORDER BY u.last_active DESC
''').fetchall()

print(f'Всего пользователей: {len(rows)}')
print()
print(f'{"vk_id":<12} {"имя":<18} {"попыток":<9} {"верных":<8} {"ОГЭ":<6} {"ЕГЭ проф":<10} {"ЕГЭ база":<10} {"активность"}')
print('-' * 85)
for r in rows:
    print(f'{str(r[0]):<12} {str(r[1] or "-"):<18} {str(r[3]):<9} {str(r[4] or 0):<8} '
          f'{str(r[5] or 0):<6} {str(r[6] or 0):<10} {str(r[7] or 0):<10} {str(r[2] or "-")[:16]}')

con.close()