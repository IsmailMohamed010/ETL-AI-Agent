import pandas as pd
import mysql.connector
import os


def receive_transformed_file(file_path):
    """
    Reads a transformed CSV file using pandas.
    
    Args:
        file_path (str): Path to the CSV file
        
    Returns:
        pd.DataFrame: The data from the CSV file
    """
    df = pd.read_csv(file_path)
    print(f"Successfully read transformed file: {file_path}")
    return df


def save_file_to_project_folder(df, project_name):
    """
    Creates a folder inside "projects" directory using the project name.
    Saves the DataFrame as "data.csv" inside that folder.
    
    Args:
        df (pd.DataFrame): The DataFrame to save
        project_name (str): Name of the project folder
        
    Returns:
        str: The saved file path
    """
    # Create final result folder if it doesn't exist
    projects_dir = "final result"
    if not os.path.exists(projects_dir):
        os.makedirs(projects_dir)
    
    # Create project-specific folder
    project_folder = os.path.join(projects_dir, project_name)
    if not os.path.exists(project_folder):
        os.makedirs(project_folder)
    
    # Save DataFrame as CSV
    file_path = os.path.join(project_folder, "data.csv")
    df.to_csv(file_path, index=False)
    print(f"Successfully saved data to: {file_path}")
    
    return file_path


def create_database_from_file(file_path):
    """
    Reads a CSV file and inserts the data into a MySQL database.
    Creates the database and project_data table automatically if they do not exist.
    
    Args:
        file_path (str): Path to the CSV file
    """
    # Read CSV file
    df = pd.read_csv(file_path)
    
    # Connect to MySQL without specifying a database
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="100100"
    )
    
    cursor = conn.cursor()
    
    # Create database if it doesn't exist
    cursor.execute("CREATE DATABASE IF NOT EXISTS `final db`")
    cursor.close()
    conn.close()
    
    # Now connect to the created database
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="100100",
        database="final db"
    )
    
    cursor = conn.cursor()
    
    # Create table if it doesn't exist
    columns = df.columns.tolist()
    
    # Build column definitions (no auto-increment, use the CSV columns as-is)
    column_defs = []
    for col in columns:
        if col.lower() == 'id':
            column_defs.append(f"`{col}` INT PRIMARY KEY")
        else:
            column_defs.append(f"`{col}` VARCHAR(255)")
    
    create_table_query = f"""
        CREATE TABLE IF NOT EXISTS project_data (
            {', '.join(column_defs)}
        )
    """
    cursor.execute(create_table_query)
    
    # Clear existing data
    cursor.execute("TRUNCATE TABLE project_data")
    
    # Insert data into the table
    placeholders = ', '.join(['%s'] * len(columns))
    insert_query = f"INSERT INTO project_data ({', '.join([f'`{col}`' for col in columns])}) VALUES ({placeholders})"
    
    for _, row in df.iterrows():
        cursor.execute(insert_query, tuple(row))
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"Successfully inserted data into MySQL database: final db")
