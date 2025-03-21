import sys
from backend.utils.csv_utils import search_field_in_files

directory_path = sys.argv[1]
search_term = sys.argv[2]

headers, rows = search_field_in_files(directory_path, search_term)

print(f"Headers: {headers}")
print(f"Rows: {rows}")
