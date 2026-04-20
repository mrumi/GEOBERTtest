
from preprocessing.fetch_data import init_db, ingest_gse_list
from preprocessing.split_data import split_gse_record
from preprocessing.create_json import save_study_json

if __name__ == "__main__":

    DB_PATH = "/content/geo_data.db"
    
    init_db(DB_PATH)
    retina_gse_list = [ "GSE293983", "GSE288573", "GSE298665",
                       "GSE254430", "GSE306375", "GSE261489",
                        'GSE310817', 'GSE301140', 'GSE313101',
                        'GSE313071', 'GSE313068', 'GSE313067'
    ]
    ingest_gse_list(retina_gse_list, DB_PATH)
