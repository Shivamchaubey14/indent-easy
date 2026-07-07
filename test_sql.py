import pymysql
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

def generate_combined_sql(output_file):
    # Get database configuration from environment variables
    db_host = os.getenv('DATABASE_HOST')
    db_user = os.getenv('DATABASE_USER')
    db_password = os.getenv('DATABASE_PASSWORD')
    db_name = os.getenv('DATABASE_NAME')
    db_port = os.getenv('DATABASE_PORT')

    print("DB_HOST:", db_host)
    print("DB_USER:", db_user)
    print("DB_PASSWORD:", db_password)
    print("DB_NAME:", db_name)
    print("DB_PORT:", db_port)

    # Connect to the MySQL database
    connection = pymysql.connect(
        host=db_host,
        user=db_user,
        password=db_password,
        database=db_name,
        port=int(db_port)
    )
    cursor = connection.cursor()

    # Generate SQL for main_app_product
    cursor.execute("SELECT name, size FROM main_app_product;")
    product_rows = cursor.fetchall()

    product_sql = "INSERT INTO main_app_product (name, size)\nVALUES\n"
    product_values = []
    for row in product_rows:
        name = f'"{row[0].replace("'", "''")}"'
        size = "NULL" if row[1] is None else f'"{row[1].replace("'", "''")}"'
        product_values.append(f"({name}, {size})")
    product_sql += ",\n".join(product_values) + ";"

    # Generate SQL for main_app_vendor
    cursor.execute("SELECT name, email FROM main_app_vendor;")
    vendor_rows = cursor.fetchall()

    vendor_sql = "INSERT INTO main_app_vendor (name, email)\nVALUES\n"
    vendor_values = []
    for row in vendor_rows:
        name = f'"{row[0].replace("'", "''")}"'
        email = f'"{row[1].replace("'", "''")}"' if row[1] else "NULL"
        vendor_values.append(f"({name}, {email})")
    vendor_sql += ",\n".join(vendor_values) + ";"

    # Generate SQL for main_app_productvendor
    cursor.execute("SELECT product_id, vendor_id FROM main_app_productvendor;")
    productvendor_rows = cursor.fetchall()

    productvendor_sql = "INSERT INTO main_app_productvendor (product_id, vendor_id, added_at)\nVALUES\n"
    productvendor_values = []
    for row in productvendor_rows:
        product_id = row[0]
        vendor_id = row[1]
        productvendor_values.append(f"({product_id}, {vendor_id}, CURRENT_TIMESTAMP)")
    productvendor_sql += ",\n".join(productvendor_values) + ";"

    # Combine all SQL statements into one file
    with open(output_file, 'w') as file:
        file.write(product_sql + "\n\n")
        file.write(vendor_sql + "\n\n")
        file.write(productvendor_sql)

    # Close the connection
    cursor.close()
    connection.close()
    print(f"Combined SQL file generated: {output_file}")

# Output file name
output_file = 'output.sql'

# Generate the combined SQL file
generate_combined_sql(output_file)
