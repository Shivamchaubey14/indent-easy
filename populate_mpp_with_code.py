import os
import django
import pandas as pd
from django.db import transaction

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'shwetDhara_project.settings')
django.setup()

# Import models after Django setup
from main_app.models import BMCOrMCC, MPPWithCode

# Path to the Excel file
EXCEL_FILE_PATH = r"C:\Users\Shwetdhara\Desktop\MPPDetails_B2A56A6F6DD44EC6BE78844294C52784.xlsx"

def populate_mpp_with_code():
    # Check if the file exists
    if not os.path.exists(EXCEL_FILE_PATH):
        print(f"Error: File not found at {EXCEL_FILE_PATH}")
        return

    # Load the Excel file into a DataFrame
    try:
        df = pd.read_excel(EXCEL_FILE_PATH)
        print(f"Excel file loaded successfully. Total rows: {len(df)}")
        print(f"Columns found: {df.columns.tolist()}")
    except Exception as e:
        print(f"Error reading Excel file: {e}")
        return

    # Ensure required columns are present
    required_columns = ["bmc_name", "mpp_ex_code", "mpp_name"]
    if not all(col in df.columns for col in required_columns):
        print(f"Error: Excel file must contain the following columns: {required_columns}")
        print(f"Available columns: {df.columns.tolist()}")
        return

    # Remove rows with missing critical data
    df = df.dropna(subset=["bmc_name", "mpp_ex_code", "mpp_name"])
    print(f"Rows after removing missing data: {len(df)}")

    # Strip whitespace from string columns
    df["bmc_name"] = df["bmc_name"].str.strip()
    df["mpp_ex_code"] = df["mpp_ex_code"].astype(str).str.strip()
    df["mpp_name"] = df["mpp_name"].str.strip()

    try:
        with transaction.atomic():
            bmc_created_count = 0
            mpp_created_count = 0
            mpp_updated_count = 0

            # Get unique BMC names from the Excel file
            unique_bmcs = df["bmc_name"].unique()
            
            for bmc_name in unique_bmcs:
                # Create or get the BMC/MCC entry
                bmc, bmc_created = BMCOrMCC.objects.get_or_create(name=bmc_name)
                if bmc_created:
                    bmc_created_count += 1
                    print(f"Created BMC/MCC: {bmc_name}")

                # Filter rows for this BMC
                bmc_rows = df[df["bmc_name"] == bmc_name]

                for _, row in bmc_rows.iterrows():
                    # Concatenate mpp_ex_code and mpp_name
                    name_with_code = f"{row['mpp_ex_code']} {row['mpp_name']}"

                    # Create or update the MPPWithCode entry
                    mpp, created = MPPWithCode.objects.update_or_create(
                        bmc_or_mcc=bmc,
                        name_with_code=name_with_code,
                        defaults={}  # Add any other fields to update here if needed
                    )
                    
                    if created:
                        mpp_created_count += 1
                    else:
                        mpp_updated_count += 1

            print("\n" + "="*50)
            print("Population completed successfully!")
            print(f"BMCs/MCCs created: {bmc_created_count}")
            print(f"MPPs created: {mpp_created_count}")
            print(f"MPPs updated: {mpp_updated_count}")
            print("="*50)
            
    except Exception as e:
        print(f"Error populating the table: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    populate_mpp_with_code()