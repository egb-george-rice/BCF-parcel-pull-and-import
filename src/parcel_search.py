import sys
import requests
import geopandas as gpd
from shapely import wkt
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QLineEdit, QMessageBox, QFileDialog
import os
import logging
import subprocess

# Setup logging for debugging purposes
logging.basicConfig(level=logging.DEBUG, filename='debug.log', filemode='w',
                    format='%(asctime)s - %(levelname)s - %(message)s')

# API and authentication details
client_key = 'RqMXhNFKlQ'  # Replace with your actual client token
api_version = '9'  # API version
api_url = "https://reportallusa.com/api/parcels"


class ReportAllParcelSearch(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('ReportAll Parcel Search')

        # Input fields for new query option
        self.county_id_label = QLabel('County ID:', self)
        self.county_id_input = QLineEdit(self)
        self.owner_label = QLabel('Owner (optional)(";" for multiple values):', self)
        self.owner_input = QLineEdit(self)
        self.parcel_id_label = QLabel('Parcel ID (optional)(";" for multiple values):', self)
        self.parcel_id_input = QLineEdit(self)
        self.calc_acreage_min_label = QLabel('Minimum Acreage (optional):', self)
        self.calc_acreage_min_input = QLineEdit(self)

        # Run and Exit buttons
        self.run_button = QPushButton('Run', self)
        self.run_button.clicked.connect(self.run_action)
        self.exit_button = QPushButton('Exit', self)
        self.exit_button.clicked.connect(self.close)

        # Layout
        vbox = QVBoxLayout()
        vbox.addWidget(QLabel("Enter the query details:"))
        vbox.addWidget(self.county_id_label)
        vbox.addWidget(self.county_id_input)
        vbox.addWidget(self.owner_label)
        vbox.addWidget(self.owner_input)
        vbox.addWidget(self.parcel_id_label)
        vbox.addWidget(self.parcel_id_input)
        vbox.addWidget(self.calc_acreage_min_label)
        vbox.addWidget(self.calc_acreage_min_input)
        hbox = QVBoxLayout()
        hbox.addWidget(self.run_button)
        hbox.addWidget(self.exit_button)
        vbox.addLayout(hbox)


        self.setLayout(vbox)
        self.show()

    def run_action(self):
        county_id = self.county_id_input.text().strip()
        owner = self.owner_input.text().strip()
        parcel_id = self.parcel_id_input.text().strip()
        calc_acreage_min = self.calc_acreage_min_input.text().strip()

        if not county_id:
            QMessageBox.warning(self, 'Error', 'County ID is required for a new query.')
            return

        self.run_new_query(county_id, owner, parcel_id, calc_acreage_min)

    def run_new_query(self, county_id, owner, parcel_id, calc_acreage_min):
        params = {
            'client': client_key,
            'v': api_version,
            'county_id': county_id,
            'owner': owner,
            'parcel_id': parcel_id,
            'calc_acreage_min': calc_acreage_min,
            'returnGeometry': 'true',
            'f': 'geojson',
            'page': 1
        }
        all_results = []
        try:
            while True:
                response = requests.get(api_url, params=params)
                response.raise_for_status()
                data = response.json()

                if 'results' in data and data['results']:
                    all_results.extend(data['results'])
                    if data['count'] > len(all_results):
                        params['page'] += 1
                        continue
                    else:
                        break
                else:
                    break

            if all_results:
                # Ensure 'geom_as_wkt' exists and matches the number of rows
                valid_results = [res for res in all_results if 'geom_as_wkt' in res]
                geometries = [wkt.loads(res['geom_as_wkt']) for res in valid_results]
                gdf = gpd.GeoDataFrame(valid_results, geometry=geometries)
                gdf.crs = "EPSG:4326"
                self.display_results(gdf)
            else:
                QMessageBox.warning(self, 'No Results', 'No parcels found for the specified query.')
        except requests.exceptions.RequestException as e:
            QMessageBox.critical(self, 'Error', f'Error querying the API: {str(e)}')
            logging.error(f'Error querying the API with URL: {api_url}, params: {params}, error: {str(e)}')

    def display_results(self, gdf):
        if not gdf.empty:
            self.close()  # Close the initial dialog before saving the file

            # Extract the county name and state abbreviation from the GeoDataFrame
            if 'county_name' in gdf.columns:
                county_name = gdf['county_name'].iloc[0]
            else:
                QMessageBox.warning(self, 'Error', 'County name not found in the data.')
                return

            if 'state_abbr' in gdf.columns:
                state_abbr = gdf['state_abbr'].iloc[0]
            else:
                QMessageBox.warning(self, 'Error', 'State abbreviation not found in the data.')
                return

            # Create directories
            desktop_path = os.path.join(os.path.expanduser('~'), 'Desktop', 'Parcel files')
            state_folder = os.path.join(desktop_path, state_abbr)
            county_folder = os.path.join(state_folder, f"{county_name} {state_abbr}")

            # Ensure directories exist
            os.makedirs(county_folder, exist_ok=True)

            # Construct the file name
            file_name = f"{county_name}Co{state_abbr}.gpkg"
            save_path = os.path.join(county_folder, file_name)

            # Save the GeoDataFrame to the specified path
            gdf.to_file(save_path, driver='GPKG')

            # Count of records
            record_count = len(gdf)

            # Success message including record count
            QMessageBox.information(self, 'Success',
                                    f'GeoPackage saved to {save_path}.\nNumber of records: {record_count}')
            self.ask_for_proximity_analysis(save_path, gdf)
        else:
            QMessageBox.warning(self, 'No Data', 'There is no data to save.')
            self.close_application()

    def ask_for_proximity_analysis(self, save_path, gdf):
        response = QMessageBox.question(self, 'Transmission Line Proximity Analysis',
                                        "Would you like to run a Transmission Line Proximity Analysis?",
                                        QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if response == QMessageBox.Yes:
            self.run_proximity_analysis(save_path)
        else:
            self.close_application()

    def run_proximity_analysis(self, save_path):
        try:
            script_path = os.path.join(os.path.dirname(__file__), 'tx_prox_analysis.py')
            if not os.path.exists(script_path):
                QMessageBox.critical(self, 'Error', f'Script {script_path} not found.')
                return

            # Run the 'tx_prox_analysis.py' script and pass the save_path
            subprocess.run([sys.executable, script_path, save_path], check=True)
        except subprocess.CalledProcessError as e:
            QMessageBox.critical(self, 'Error', f'Error running the proximity analysis: {str(e)}')
            logging.error(f'Error running the proximity analysis with script: {script_path}, error: {str(e)}')
        finally:
            self.close_application()
            QApplication.quit()  # Quit the application completely

    def close_application(self):
        self.close()  # Close the QWidget


def main():
    app = QApplication(sys.argv)
    gui = ReportAllParcelSearch()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
