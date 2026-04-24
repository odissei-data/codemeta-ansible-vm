import pandas as pd

# List of files to process
files = [
    'experiments - Dataverse-FAIRChecker.csv',
    'experiments - Dataverse-Fuji-0.5.csv',
    'experiments - Dataverse-Fuji-0.8.csv'
]

# Dictionary defining the string-to-numeric mapping
conversion_map = {
    "2 of 2": 1.0,
    "0.5 of 1": 0.5,
    "1 of 1": 1.0,
    "1 of 2": 0.5,
    "0 of 2": 0.0,
    "0 of 1": 0.0,
    "3 of 4": 0.75
}

def convert_csv_files(file_list, mapping):
    """
    Reads a list of CSV files, replaces specified strings with numeric values,
    and saves the result to new CSV files.
    """
    for file_name in file_list:
        try:
            # Read the CSV file
            df = pd.read_csv(file_name)
            
            # Replace the fractional strings with numbers across the entire dataframe
            df_numeric = df.replace(mapping)
            
            # Define output filename with a prefix
            output_name = f"numeric_{file_name}"
            
            # Save the transformed data
            df_numeric.to_csv(output_name, index=False)
            print(f"Successfully converted and saved: {output_name}")
            
        except FileNotFoundError:
            print(f"File not found: {file_name}")
        except Exception as e:
            print(f"An error occurred while processing {file_name}: {e}")

if __name__ == "__main__":
    convert_csv_files(files, conversion_map)