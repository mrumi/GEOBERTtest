import os
from pathlib import Path
import json

from preprocessing.fetching import init_db, ingest_gse_list, convert_json
from preprocessing.spliting import ensure_dirs, split_gse_record
from preprocessing.JSONmaking import save_study_json, save_samples_json

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

    json_processed_dir = "../output/processed_data/"
    json_processed_dir = Path(json_processed_dir)
    json_processed_dir.mkdir(parents=True, exist_ok=True)
    
    ensure_dirs(json_processed_dir)

    with open(out_json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict):
        data = [data]

    for gse in data:
        split_gse_record(gse, json_processed_dir)

    print(f"✅ Finished processing {len(data)} GSE record(s)")


    raw_file_dir = os.path.join(json_processed_dir, "raw")
    processed_files = Path(raw_file_dir).glob('*.raw.json')
    study_out_dir = os.path.join(output_dir, "semantic_studies")
    sample_out_dir = os.path.join(output_dir, "semantic_samples")
    
    for file in processed_files:
        save_study_json(raw_json_path = file, output_dir = study_out_dir)
        save_samples_json(raw_json_path = file, output_dir = sample_out_dir)
        
    print(f"✅ Finished making jsons for all processed studies and corresponding samples")
