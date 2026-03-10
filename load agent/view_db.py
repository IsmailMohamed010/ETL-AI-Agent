import mysql.connector
import pandas as pd

# Connect to MySQL database
conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="100100",
    database="final db"
)

cursor = conn.cursor()

# Query the project_data table
cursor.execute("SELECT * FROM project_data")
results = cursor.fetchall()

# Get column names
column_names = [description[0] for description in cursor.description]

# Create a DataFrame for better visualization
df = pd.DataFrame(results, columns=column_names)

print("=" * 60)
print("DATABASE: final db")
print("TABLE: project_data")
print("=" * 60)
print(df.to_string(index=False))
print("=" * 60)
print(f"Total records: {len(results)}")

cursor.close()
conn.close()
