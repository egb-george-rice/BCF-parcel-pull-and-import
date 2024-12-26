import os
import sys
import time
import json
import logging
import requests
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional

# Tkinter import with error handling for different environments
try:
    import tkinter as tk
    from tkinter import filedialog
except ImportError:
    tk = None
    filedialog = None

# Ensure environment variable loading for API key
API_KEY = os.getenv('MONDAY_API_KEY', '')  # Load from environment variable

if not API_KEY:
    raise ValueError("Monday.com API key is not set. Please set it in the environment variable 'MONDAY_API_KEY'.")


class CSVProcessor:
    def __init__(self):
        # Set up logging
        log_directory = self._get_log_directory()
        os.makedirs(log_directory, exist_ok=True)
        log_path = os.path.join(log_directory, 'clean_csv_debug.log')

        logging.basicConfig(
            level=logging.DEBUG,
            filename=log_path,
            filemode='w',
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

        self.monday_config = {
            'api_url': "https://api.monday.com/v2",
            'api_key': API_KEY,
            'board_id': "6037891323"
        }

    def _get_log_directory(self):
        """Determine the appropriate directory for log files"""
        if getattr(sys, 'frozen', False):
            # If the application is run as a bundle, use the executable's directory
            return os.path.dirname(sys.executable)
        else:
            # If run as a script, use the script's directory
            return os.path.dirname(os.path.abspath(__file__))

    def get_input_file(self) -> tuple[str, str]:
        """
        Get input file path either from command line or file dialog.
        Handles environments with or without GUI
        """
        # Check if file path was provided as command line argument
        if len(sys.argv) > 1:
            input_path = sys.argv[1]
            if os.path.exists(input_path):
                directory = os.path.dirname(input_path)
                filename = os.path.basename(input_path)
                name, ext = os.path.splitext(filename)
                output_path = os.path.join(directory, f"{name}_clean{ext}")

                self.logger.info(f"Using provided input file: {input_path}")
                return input_path, output_path

        # Fallback to file dialog if tkinter is available
        if tk and filedialog:
            root = tk.Tk()
            root.withdraw()

            input_path = filedialog.askopenfilename(
                title="Select CSV file to process",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )

            if not input_path:
                print("No file selected. Exiting...")
                sys.exit(0)

            directory = os.path.dirname(input_path)
            filename = os.path.basename(input_path)
            name, ext = os.path.splitext(filename)
            output_path = os.path.join(directory, f"{name}_clean{ext}")

            return input_path, output_path

        # If no GUI and no command line argument
        print("No input file specified. Please provide a CSV file path.")
        sys.exit(1)

    def verify_board_exists(self):
        """Verify that the board exists and we have access to it"""
        query = """
        query {
            boards(ids: %s) {
                id
                name
                state
            }
        }
        """ % self.monday_config['board_id']

        response = requests.post(
            self.monday_config['api_url'],
            json={"query": query},
            headers={
                "Authorization": self.monday_config['api_key'],
                "Content-Type": "application/json",
            }
        )

        print("\nBoard verification:")
        print(f"Response: {response.text}")
        return response.status_code == 200 and response.json().get('data', {}).get('boards')

    def create_group(self, county: str, state: str) -> str:
        """Create a new group on the Monday.com board"""
        today = datetime.now().strftime("%Y-%m-%d")
        group_title = f"{county} County, {state}: {today}"

        mutation = """
        mutation {
            create_group (
                board_id: %s,
                group_name: "%s"
            ) {
                id
            }
        }
        """ % (self.monday_config['board_id'], group_title)

        response = requests.post(
            self.monday_config['api_url'],
            json={"query": mutation},
            headers={
                "Authorization": self.monday_config['api_key'],
                "Content-Type": "application/json",
            }
        )

        if response.status_code == 200:
            data = response.json()
            if 'data' in data and 'create_group' in data['data']:
                return data['data']['create_group']['id']
        return None

    def format_monday_column_value(self, value, column_type):
        """Format values according to Monday.com's column type requirements"""
        if pd.isna(value):
            return ""

        if column_type == "number":
            # For numeric columns, return number directly
            try:
                return str(float(value))
            except (ValueError, TypeError):
                return "0"
        elif column_type == "text":
            return str(value)
        elif column_type == "long_text":
            return {"text": str(value)}
        elif column_type == "dropdown":
            return {"labels": [str(value)]}
        else:
            return str(value)

    def format_county_id(self, value):
        """Format county_id to ensure it's always 5 digits with leading zeros"""
        try:
            cleaned = ''.join(filter(str.isdigit, str(value)))
            return cleaned.zfill(5)
        except Exception as e:
            print(f"Error formatting county_id: {e}")
            return "00000"

    def import_to_monday(self, df: pd.DataFrame) -> None:
        """Import processed data to Monday.com with explicit status settings"""
        print(f"Starting import of {len(df)} records to Monday.com...")

        # Verify board access first
        if not self.verify_board_exists():
            print("Error: Cannot access the specified board. Please verify the board ID and permissions.")
            return

        headers = {
            "Authorization": self.monday_config['api_key'],
            "Content-Type": "application/json",
        }

        successful_imports = 0
        failed_imports = 0
        total_rows = len(df)

        # Get the first row to determine county and state for group creation
        first_row = df.iloc[0]
        group_id = self.create_group(
            first_row.get('county_name', 'Unknown'),
            first_row.get('state_abbr', 'XX')
        )

        if not group_id:
            print("Failed to create group. Aborting import.")
            return

        for idx, row in df.iterrows():
            try:
                # [Rest of the existing import code remains the same until the response handling]

                if response.status_code == 200:
                    response_data = response.json()
                    if 'data' in response_data and response_data['data'].get('create_item'):
                        successful_imports += 1
                        print(f"Successfully imported row {idx + 1}")
                    else:
                        failed_imports += 1
                        print(f"Failed to import row {idx + 1}. Response: {response_data}")
                else:
                    failed_imports += 1
                    print(f"Failed to import row {idx + 1}. Status code: {response.status_code}")

                time.sleep(0.5)  # Rate limiting

            except Exception as e:
                failed_imports += 1
                print(f"Error importing row {idx + 1}: {str(e)}")
                continue

        # Enhanced completion message with detailed statistics
        print("\n" + "=" * 50)
        print("IMPORT COMPLETION ACKNOWLEDGEMENT")
        print("=" * 50)
        print(f"\nImport process completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"\nSummary of Import Results:")
        print(f"• Total records processed: {total_rows}")
        print(f"• Successfully imported: {successful_imports} records")
        print(f"• Failed imports: {failed_imports} records")
        print(f"• Success rate: {(successful_imports / total_rows * 100):.1f}%")

        if successful_imports > 0:
            print("\nData has been successfully imported to your Monday.com board.")
            print(f"You can view your {successful_imports} new records at:")
            print(f"https://brightcleanfuture.monday.com/boards/{self.monday_config['board_id']}")

        if failed_imports > 0:
            print("\nTroubleshooting steps for failed imports:")
            print("1. Check your internet connection")
            print("2. Verify the Monday.com API key permissions")
            print("3. Review the log file for detailed error messages")
            print("4. Contact support if issues persist")

        print("\nThank you for using the Monday.com Import Tool!")
        print("=" * 50)


def process_csv(file_path: str = None):
    """Process a CSV file and import to Monday.com. Can be called with or without a file path."""
    processor = None
    try:
        processor = CSVProcessor()
        processor.logger.info("Starting CSV processing")

        if file_path:
            # Direct file processing (for tx_prox_analysis)
            if not os.path.exists(file_path):
                print(f"Error: File not found: {file_path}")
                return False

            directory = os.path.dirname(file_path)
            filename = os.path.basename(file_path)
            name, ext = os.path.splitext(filename)
            output_path = os.path.join(directory, f"{name}_clean{ext}")
            processor.logger.info(f"Using direct file path: {file_path}")
        else:
            # GUI file selection (for process launcher)
            file_path, output_path = processor.get_input_file()
            processor.logger.info(f"File selected via GUI: {file_path}")

        # Read and process CSV
        print(f"Reading file: {file_path}")
        processor.logger.info(f"Starting to read CSV: {file_path}")
        df = pd.read_csv(file_path)
        total_records = len(df)
        processor.logger.info(f"CSV file loaded successfully with {len(df)} rows")

        # Import to Monday.com
        print("\nImporting to Monday.com...")
        processor.logger.info("Starting Monday.com import")
        processor.import_to_monday(df)

        print("\nProcessing complete!")
        processor.logger.info("Processing completed successfully")

        # Brief pause to ensure logs are written
        time.sleep(1)

        # Return success indicator and record count to the launcher
        return True, total_records

    except Exception as e:
        error_msg = f"An error occurred: {str(e)}"
        print(f"\n{error_msg}")
        if processor and processor.logger:
            processor.logger.error(error_msg)
        return False, 0

if __name__ == "__main__":
    try:
        # If called directly, use command line argument or GUI selection
        file_path = sys.argv[1] if len(sys.argv) > 1 else None
        success, total_records = process_csv(file_path)
        if success:
            print(f"\nSuccessfully processed {total_records} records.")
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\nCritical error: {str(e)}")
        sys.exit(1)