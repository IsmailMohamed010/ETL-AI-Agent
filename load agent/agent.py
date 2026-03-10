from functions import receive_transformed_file, save_file_to_project_folder, create_database_from_file


class LoadAgent:
    """
    A simple agent for loading and processing transformed data files.
    """
    
    def run(self, file_path, project_name):
        """
        Executes the load pipeline:
        1. Reads the transformed CSV file
        2. Saves the data to a project folder
        3. Creates a SQLite database from the file
        
        Args:
            file_path (str): Path to the transformed CSV file
            project_name (str): Name of the project
        """
        # Step 1: Receive and read the transformed file
        df = receive_transformed_file(file_path)
        
        # Step 2: Save the file to the project folder
        saved_path = save_file_to_project_folder(df, project_name)
        
        # Step 3: Create database from the file
        create_database_from_file(saved_path)
        
        # Print success message
        print("Pipeline finished successfully")
