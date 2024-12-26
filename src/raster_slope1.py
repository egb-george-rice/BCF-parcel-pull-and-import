import os
import sys
import rasterio
import geopandas as gpd
import requests
import fiona
from rasterio.warp import calculate_default_transform, reproject, Resampling
import rasterio.features
import numpy as np
from tkinter import Tk
from tkinter.filedialog import askopenfilename
from shapely.geometry import shape, mapping
import traceback
import datetime

# Hard-coded API Key for OpenTopography
API_KEY = 'b0947fbc1a5133959e9496208e5c3499'


def main():
    """Main entry point for the script"""
    try:
        # Check if file path was passed as argument
        if len(sys.argv) > 1:
            input_file = sys.argv[1]
            # Remove any quotes and normalize path
            input_file = input_file.strip('"').strip("'")
            input_file = os.path.normpath(input_file)
        else:
            # If no argument, use GUI
            Tk().withdraw()
            input_file = askopenfilename(filetypes=[("GeoPackage Files", "*.gpkg")])
            if not input_file:
                print("No file selected. Exiting...")
                return 1

        # Validate input file
        if not os.path.exists(input_file):
            print(f"Error: Input file not found: {input_file}")
            return 1

        # Create output paths
        base_dir = os.path.dirname(input_file)
        base_name = os.path.splitext(os.path.basename(input_file))[0]
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        # Create temp and output files
        temp_dem = os.path.join(base_dir, f"{base_name}_dem_{timestamp}.tif")
        reprojected_dem = os.path.join(base_dir, f"{base_name}_reproj_{timestamp}.tif")
        resampled_dem = os.path.join(base_dir, f"{base_name}_resampled_{timestamp}.tif")
        slope_raster = os.path.join(base_dir, f"{base_name}_slope_{timestamp}.tif")
        output_shapefile = os.path.join(base_dir, f"{base_name}_slope.shp")

        # Process the file
        print(f"Processing file: {input_file}")
        print("Getting extent from input file...")
        gdf = gpd.read_file(input_file)
        extent = gdf.total_bounds

        print("Downloading DEM...")
        url = "https://portal.opentopography.org/API/globaldem"
        params = {
            'demtype': 'SRTMGL1',
            'south': extent[1],
            'north': extent[3],
            'west': extent[0],
            'east': extent[2],
            'outputFormat': 'GTiff',
            'API_Key': API_KEY
        }

        response = requests.get(url, params=params)
        if response.status_code == 200:
            with open(temp_dem, 'wb') as f:
                f.write(response.content)
            print("DEM downloaded successfully")
        else:
            print(f"Failed to download DEM. Status code: {response.status_code}")
            print(response.text)
            return 1

        print("Processing DEM...")
        reproject_raster(temp_dem, reprojected_dem)
        resample_dem(reprojected_dem, resampled_dem)
        calculate_slope(resampled_dem, slope_raster)
        raster_to_shapefile(slope_raster, output_shapefile)

        # Clean up temporary files
        temp_files = [temp_dem, reprojected_dem, resampled_dem, slope_raster]
        for file in temp_files:
            if os.path.exists(file):
                os.remove(file)
                print(f"Removed temporary file: {file}")

        print(f"Successfully created: {output_shapefile}")
        return 0

    except Exception as e:
        print(f"Error: {str(e)}")
        traceback.print_tb(e.__traceback__)
        return 1


# [Keep all your other functions (calculate_slope, reproject_raster, etc.) exactly as they were]

if __name__ == '__main__':
    sys.exit(main())