from agent import LoadAgent

# NOTE: Make sure MySQL is running and the following setup is complete:
# 1. MySQL server is running on localhost
# 2. Database "projects_db" exists (can be created with: CREATE DATABASE projects_db;)
# 3. If needed, update the username/password in functions.py create_database_from_file()

# Create an instance of the LoadAgent
agent = LoadAgent()

# Define the file path and project name
file_path = "Transformtion/output.csv"
project_name = "ExampleProject"

# Run the agent pipeline
agent.run(file_path, project_name)
