import os
from pathlib import Path

from preprocessing.fetch_data import init_db, ingest_gse_list, convert_json
from preprocessing.split_data import split_gse_record
from preprocessing.create_json import save_study_json

if __name__ == "__main__":

    output_dir = "../output/"
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    database_path = os.path.join(output_dir, "geo_data.db")
    init_db(database_path)

    # this will be changed to reading from file, temorarily manual
    retina_gse_list = [ "GSE293983", "GSE288573", "GSE298665",
                       "GSE254430", "GSE306375", "GSE261489",
                        'GSE310817', 'GSE301140', 'GSE313101',
                        'GSE313071', 'GSE313068', 'GSE313067'
    ]
    
    ingest_gse_list(retina_gse_list, database_path)

    out_json_file = os.path.join(output_dir, "gse_data.json")
    convert_json(database_path, out_json_file)

    #INPUT_JSON_PATH = ""   # your original file
    #OUTPUT_BASE_DIR = "processed_data"

    data_dir = "../output/"
    data_dir.mkdir(parents=True, exist_ok=True)
    
    ensure_dirs(OUTPUT_BASE_DIR)

    with open(INPUT_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict):
        data = [data]

    for gse in data:
        split_gse_record(gse, OUTPUT_BASE_DIR)

    print(f"✅ Finished processing {len(data)} GSE record(s)")

