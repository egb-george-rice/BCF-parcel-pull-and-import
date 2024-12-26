import sys
import os
import geopandas as gpd
import pandas as pd
from tkinter import filedialog, messagebox, ttk
import tkinter as tk
from pathlib import Path
import threading
import subprocess
import logging
from shapely.ops import nearest_points
from geopandas.tools import sjoin_nearest

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='transmission_analysis.log'
)


class TransmissionLineAnalysis:
    def __init__(self, root, input_file=None):
        self.root = root
        self.root.title("Transmission Line Analysis")
        self.input_file = input_file
        self.script_thread = None
        self.cancel_requested = False
        self.intermediate_files = []
        self.keep_files = []

        # Initialize UI
        self.setup_ui()

        if self.input_file:
            self.file_label.config(text=f"Selected file: {self.input_file}")
            self.root.after(100, self.start_processing)
        else:
            self.browse_file()

    def setup_ui(self):
        """Setup the UI components"""
        self.frame = tk.Frame(self.root, padx=20, pady=20)
        self.frame.pack(expand=True, fill='both')

        # File selection
        file_frame = tk.Frame(self.frame)
        file_frame.pack(fill='x', pady=(0, 10))

        self.label = tk.Label(file_frame, text="Select .gpkg or .shp file:")
        self.label.pack(side='left')

        self.file_button = tk.Button(file_frame, text="Browse", command=self.browse_file)
        self.file_button.pack(side='right', padx=5)

        # File label
        self.file_label = tk.Label(self.frame, text="", wraplength=400)
        self.file_label.pack(fill='x', pady=5)

        # Progress bar
        self.progress = tk.DoubleVar()
        self.progressbar = ttk.Progressbar(
            self.frame, length=400, variable=self.progress, mode='determinate'
        )
        self.progressbar.pack(fill='x', pady=5)

        self.progress_label = tk.Label(self.frame, text="0%")
        self.progress_label.pack(pady=5)

        # Buttons
        button_frame = tk.Frame(self.frame)
        button_frame.pack(fill='x', pady=10)

        self.start_button = tk.Button(
            button_frame,
            text="Start Processing",
            command=self.start_processing
        )
        self.start_button.pack(side='left', expand=True, padx=5)

        self.cancel_button = tk.Button(
            button_frame,
            text="Cancel",
            command=self.cancel_processing,
            state=tk.DISABLED
        )
        self.cancel_button.pack(side='right', expand=True, padx=5)

        self.status_label = tk.Label(self.frame, text="")
        self.status_label.pack(pady=5)

    def browse_file(self):
        """Open file dialog for selecting input file"""
        initial_dir = os.path.expanduser("~/Desktop/Parcel files")
        self.input_file = filedialog.askopenfilename(
            title="Choose file for analysis",
            filetypes=[("GeoPackage files", "*.gpkg"), ("Shapefile", "*.shp")],
            initialdir=initial_dir
        )
        if self.input_file:
            self.file_label.config(text=f"Selected file: {self.input_file}")

    def start_processing(self):
        """Start the processing thread"""
        if not self.input_file:
            messagebox.showerror("Error", "Please select an input file.")
            return

        self.status_label.config(text="Processing...")
        self.start_button.config(state=tk.DISABLED)
        self.file_button.config(state=tk.DISABLED)
        self.cancel_button.config(state=tk.NORMAL)
        self.cancel_requested = False

        self.script_thread = threading.Thread(target=self.run_analysis)
        self.script_thread.start()

    def run_analysis(self):
        """Run the analysis in a separate thread"""
        try:
            output_file, subset_file = self.process_transmission_lines()
            self.root.after(0, self.handle_analysis_result, output_file, subset_file)
        except Exception as e:
            self.root.after(0, self.handle_error, str(e))

    def process_transmission_lines(self):
        """Process the transmission lines analysis"""
        try:
            # Read input file
            parcels = gpd.read_file(self.input_file)
            if parcels.empty:
                raise ValueError("Input file contains no features")

            # Read transmission lines
            tx_file = Path(
                __file__).parent / '..' / 'GIS files' / 'General' / 'Transmission' / 'Electric_Power_Transmission_Lines.shp'
            if not tx_file.exists():
                raise FileNotFoundError(f"Transmission line file not found at: {tx_file}")

            tx_lines = gpd.read_file(tx_file)

            # Convert to a projected CRS for accurate distance measurements
            utm_zone = 17  # Adjust based on your location
            utm_crs = f"EPSG:269{utm_zone}"

            if parcels.crs != utm_crs:
                parcels = parcels.to_crs(utm_crs)
            if tx_lines.crs != utm_crs:
                tx_lines = tx_lines.to_crs(utm_crs)

            # Update progress
            self.root.after(0, self.update_progress, 25)

            # Use spatial join with nearest neighbor
            # Rename VOLTAGE column before join to avoid any naming conflicts
            tx_lines = tx_lines.rename(columns={'VOLTAGE': 'voltage_of_closest_line'})

            nearest_join = sjoin_nearest(
                parcels,
                tx_lines[['voltage_of_closest_line', 'geometry']],
                how='left',
                distance_col='distance_meters'
            )

            # Convert distance to miles and ensure voltage field is present
            nearest_join['distance_to_transmission_line_miles'] = nearest_join['distance_meters'] * 0.000621371

            # Clean up columns
            nearest_join = nearest_join.drop(['distance_meters', 'index_right'], axis=1, errors='ignore')

            # Ensure voltage is numeric
            nearest_join['voltage_of_closest_line'] = pd.to_numeric(nearest_join['voltage_of_closest_line'],
                                                                    errors='coerce')

            # Update progress
            self.root.after(0, self.update_progress, 75)

            if self.cancel_requested:
                return None, None

            # Save subset of parcels within 1 mile
            subset = nearest_join[nearest_join['distance_to_transmission_line_miles'] <= 1].copy()
            if subset.empty:
                return None, None

            # Save results
            subset_file = str(Path(self.input_file).parent /
                              (Path(self.input_file).stem + "_1m" +
                               Path(self.input_file).suffix))
            subset.to_file(subset_file)
            self.keep_files.append(subset_file)

            # Create CSV for CRM import
            csv_file = str(Path(self.input_file).parent /
                           (Path(self.input_file).stem + "_transmission_analysis.csv"))
            results_df = subset.drop(columns=['geometry'])
            results_df.to_csv(csv_file, index=False)
            self.keep_files.append(csv_file)

            # Update progress
            self.root.after(0, self.update_progress, 100)

            return subset_file, csv_file

        except Exception as e:
            logging.error(f"Error in process_transmission_lines: {str(e)}")
            raise

    def update_progress(self, value):
        """Update the progress bar and label"""
        self.progress.set(value)
        self.progress_label.config(text=f"{int(value)}%")
        self.root.update_idletasks()

    def cancel_processing(self):
        """Cancel the processing"""
        self.cancel_requested = True
        self.status_label.config(text="Cancelling...")
        self.cancel_button.config(state=tk.DISABLED)

    def handle_analysis_result(self, subset_file, csv_file):
        """Handle successful analysis completion"""
        if not subset_file or not csv_file:
            messagebox.showerror("Error", "No parcels found within 1 mile of transmission lines")
            self.cleanup_and_exit()
            return

        # Clean up intermediate files
        self.cleanup_files()

        # Hide the window
        self.root.withdraw()

        # Show results and offer CRM import
        messagebox.showinfo("Success",
                            f"Analysis completed successfully!\nParcels within 1 mile saved to: {subset_file}")

        if messagebox.askyesno("Import to CRM", "Would you like to import data to CRM?"):
            try:
                crm_script = os.path.join(os.path.dirname(__file__), 'import_to_crm.py')
                if not os.path.exists(crm_script):
                    raise FileNotFoundError("CRM import script not found")

                subprocess.Popen([sys.executable, crm_script, csv_file])

            except Exception as e:
                messagebox.showerror("Error", f"Failed to start CRM import: {str(e)}")

        self.root.quit()

    def handle_error(self, error_msg):
        """Handle errors during processing"""
        messagebox.showerror("Error", error_msg)
        self.cleanup_and_exit()

    def cleanup_files(self):
        """Clean up intermediate files but keep specified results"""
        for file_path in self.intermediate_files:
            if file_path not in self.keep_files:
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)

                    # Remove associated files for shapefiles
                    if file_path.endswith('.shp'):
                        base_path = file_path[:-4]
                        for ext in ['.shx', '.dbf', '.prj', '.cpg']:
                            associated_file = base_path + ext
                            if os.path.exists(associated_file):
                                os.remove(associated_file)
                except Exception as e:
                    logging.error(f"Error removing file {file_path}: {str(e)}")

    def cleanup_and_exit(self, should_quit=False):
        """Reset UI state and optionally quit"""
        self.start_button.config(state=tk.NORMAL)
        self.file_button.config(state=tk.NORMAL)
        self.cancel_button.config(state=tk.DISABLED)
        self.status_label.config(text="")
        self.progress.set(0)
        self.progress_label.config(text="0%")

        if should_quit:
            self.root.quit()


def main():
    """Main entry point for the application"""
    root = tk.Tk()
    app = TransmissionLineAnalysis(
        root,
        input_file=sys.argv[1] if len(sys.argv) > 1 else None
    )
    root.mainloop()


if __name__ == "__main__":
    main()