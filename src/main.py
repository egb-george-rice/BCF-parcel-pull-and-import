import os
import sys
import subprocess
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QPushButton,
                             QLabel, QMessageBox)
from PyQt5.QtCore import Qt


class ProcessLauncher(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('GIS Process Launcher')
        self.setFixedWidth(400)

        # Create layout
        layout = QVBoxLayout()
        layout.setSpacing(10)

        # Add header
        header = QLabel('Select a process to run:')
        header.setAlignment(Qt.AlignCenter)
        header.setStyleSheet('font-size: 14px; font-weight: bold; margin: 10px;')
        layout.addWidget(header)

        # Define processes with their descriptions
        self.processes = {
            'Parcel Search': {
                'script': 'parcel_search.py',
                'description': 'Search and download parcel data from ReportAll API'
            },
            'Transmission Line Proximity': {
                'script': 'tx_prox_analysis.py',
                'description': 'Analyze proximity to transmission lines'
            },
            'CRM Import': {
                'script': 'import_to_crm.py',
                'description': 'Import processed data into CRM system'
            }
        }

        # Create buttons for each process
        for process_name, details in self.processes.items():
            # Create container for process
            process_button = QPushButton(process_name)
            process_button.setFixedHeight(50)
            process_button.clicked.connect(lambda checked, name=process_name: self.launch_process(name))

            # Add description label
            description = QLabel(details['description'])
            description.setStyleSheet('color: gray; font-size: 11px;')

            layout.addWidget(process_button)
            layout.addWidget(description)

        # Add exit button
        exit_button = QPushButton('Exit')
        exit_button.clicked.connect(self.close)
        exit_button.setFixedHeight(50)
        layout.addWidget(exit_button)

        self.setLayout(layout)

    def launch_process(self, process_name):
        try:
            script_path = os.path.join(os.path.dirname(__file__),
                                       self.processes[process_name]['script'])

            if not os.path.exists(script_path):
                QMessageBox.critical(self, 'Error',
                                     f'Script {script_path} not found.')
                self.close()
                QApplication.quit()
                os._exit(1)
                return

            # If launching parcel search, hide this window
            if process_name == 'Parcel Search':
                self.hide()

            # Run the selected script
            result = subprocess.run([sys.executable, script_path],
                                    capture_output=True,
                                    text=True)

            if result.returncode != 0:
                QMessageBox.critical(self, 'Error',
                                     f'Error running {process_name}: {result.stderr}')
                self.close()
                QApplication.quit()
                os._exit(1)
                return

            # Process completed successfully
            self.close()
            QApplication.quit()
            os._exit(0)

        except Exception as e:
            QMessageBox.critical(self, 'Error',
                                 f'Unexpected error running {process_name}: {str(e)}')
            self.close()
            QApplication.quit()
            os._exit(1)


def main():
    app = QApplication(sys.argv)

    # Set application style
    app.setStyle('Fusion')

    launcher = ProcessLauncher()
    launcher.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()