import os
import geopandas as gpd
import requests
import rasterio
import numpy as np
from rasterio.enums import Resampling
from rasterio.warp import calculate_default_transform, reproject
from osgeo import ogr, osr
from scipy.ndimage import sobel
import argparse
from tkinter import Tk
from tkinter.filedialog import askopenfilename


def get_map_extent(gpkg_path):
    """Extract the bounding box of the map from the .gpkg file."""
    gdf = gpd.read_file(gpkg_path)
    bbox = gdf.total_bounds  # [minx, miny, maxx, maxy]
    return bbox


def download_dem(extent, output_file, api_key):
    """Download a DEM from the OpenTopography API based on the extent."""
    url = "https://portal.opentopography.org/API/globaldem"
    params = {
        "demtype": "SRTMGL1",  # You can try removing this or using different values
        "west": extent[0],
        "south": extent[1],
        "east": extent[2],
        "north": extent[3],
        "output": "gtiff",
        "apikey": api_key  # Add API key to the request
    }

    # Print the URL and parameters for debugging
    print(f"Request URL: {url}")
    print(f"Request Parameters: {params}")

    # Make the request
    response = requests.get(url, params=params, stream=True)

    # Check if the request was successful
    if response.status_code == 200:
        with open(output_file, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"DEM downloaded to {output_file}")
    else:
        print(f"Failed to download DEM. Status code: {response.status_code}")
        print(f"Response Text: {response.text}")
        response.raise_for_status()


def calculate_slope(dem_file, output_slope_file):
    """Calculate the slope from the DEM and save it as a new raster."""
    with rasterio.open(dem_file) as src:
        # Read the DEM data
        dem_data = src.read(1)

        # Apply Sobel filter to compute the gradient (slope)
        sx = sobel(dem_data, axis=0)  # Gradient in the x direction
        sy = sobel(dem_data, axis=1)  # Gradient in the y direction

        # Calculate slope (magnitude of gradient)
        slope = np.sqrt(sx ** 2 + sy ** 2)

        # Save slope as new raster
        profile = src.profile
        profile.update(dtype=rasterio.float32, count=1)

        with rasterio.open(output_slope_file, 'w', **profile) as dst:
            dst.write(slope.astype(rasterio.float32), 1)
        print(f"Slope raster saved to {output_slope_file}")


def raster_to_shapefile(raster_file, shapefile_path):
    """Convert a raster (slope) to a shapefile."""
    # Open raster
    with rasterio.open(raster_file) as src:
        # Create a shape layer from raster data
        transform = src.transform
        crs = src.crs
        data = src.read(1)

        # Mask the NoData values and create features from the raster
        mask = data != src.nodata
        shapes = rasterio.features.shapes(data, mask=mask, transform=transform)

        # Create the shapefile
        driver = ogr.GetDriverByName('ESRI Shapefile')
        if driver is None:
            raise RuntimeError("Shapefile driver not available.")

        # Define the shapefile path and open it
        shapefile = driver.CreateDataSource(shapefile_path)
        layer = shapefile.CreateLayer('slope', geom_type=ogr.wkbPolygon)
        field = ogr.FieldDefn('slope_value', ogr.OFTReal)
        layer.CreateField(field)

        # Add geometries and their slope values
        for geom, value in shapes:
            feature = ogr.Feature(layer.GetLayerDefn())
            feature.SetGeometry(ogr.CreateGeometryFromWkb(geom))
            feature.SetField('slope_value', value)
            layer.CreateFeature(feature)
            feature = None  # Destroy feature to free memory

        shapefile = None  # Close shapefile
    print(f"Shapefile saved to {shapefile_path}")


def get_input_file():
    """Prompt user to select a .gpkg file if not provided programmatically."""
    Tk().withdraw()  # Hide the root window
    filename = askopenfilename(title="Select a .gpkg file", filetypes=[("GeoPackage files", "*.gpkg")])

    if filename:
        return filename
    else:
        print("No file selected, exiting.")
        exit()


def prompt_for_api_key():
    """Prompt user to input their API key."""
    api_key = input("Please enter your OpenTopography API key: ").strip()
    if not api_key:
        print("API key is required. Exiting.")
        exit()
    return api_key


def main(gpkg_file):
    # Prompt user for the API key
    api_key = prompt_for_api_key()

    # Step 1: Get the map extent from the .gpkg file
    extent = get_map_extent(gpkg_file)
    print(f"Map extent: {extent}")

    # Step 2: Download the DEM from OpenTopography
    dem_output_file = gpkg_file.replace(".gpkg", "_dem.tif")
    download_dem(extent, dem_output_file, api_key)

    # Step 3: Calculate the slope of the DEM and save as a new raster
    slope_output_file = dem_output_file.replace(".tif", "_slope_raster.tif")
    calculate_slope(dem_output_file, slope_output_file)

    # Step 4: Convert the slope raster to a shapefile
    shapefile_output = slope_output_file.replace(".tif", ".shp")
    raster_to_shapefile(slope_output_file, shapefile_output)


if __name__ == "__main__":
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Process a .gpkg file to generate slope from DEM.")
    parser.add_argument(
        "-f", "--file", type=str, help="Path to the .gpkg file"
    )
    args = parser.parse_args()

    # If no file is passed programmatically, ask the user to select a file
    if args.file:
        gpkg_file_path = args.file
    else:
        gpkg_file_path = get_input_file()

    # Run the main processing function
    main(gpkg_file_path)
