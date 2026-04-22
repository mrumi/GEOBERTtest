import os
from pathlib import Path
import json
import argparse
import pandas as pd


from fetching import init_db, ingest_gse_list, convert_json
from spliting import ensure_dirs, split_gse_record
from JSONmaking import save_study_json, save_samples_json

def main(input_file, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    database_path = os.path.join(output_dir, "geo_data.db")
    init_db(database_path)

    # get the GSE accessions from the input file
    gse_data = pd.read_csv(input_file, sep = "\t")
    retina_gse_list = gse_data["Accession"].tolist()
    
    ingest_gse_list(retina_gse_list, database_path)
    print(f"✅ Finished GSE downloading")

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

    raw_file_dir = os.path.join(json_processed_dir, "raw")
    processed_files = Path(raw_file_dir).glob('*.raw.json')
    study_out_dir = os.path.join(output_dir, "semantic_studies")
    sample_out_dir = os.path.join(output_dir, "semantic_samples")
    
    for file in processed_files:
        save_study_json(raw_json_path = file, output_dir = study_out_dir)
        save_samples_json(raw_json_path = file, output_dir = sample_out_dir)
    
    print(f"✅ Finished making jsons for all studies and corresponding samples")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input", dest="input", required=True, help="Path to the input file")
    parser.add_argument("-o", "--output", dest="output", required=True, help="Path to the output directory")
    
    args = parser.parse_args()
    main(args.input, args.output)


