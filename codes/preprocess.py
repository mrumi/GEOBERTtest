
from preprocessing import fetch_data
from preprocessing import split_data
from preprocessing import create_json


if __name__ == "__main__":
    init_db()
    retina_gse_list = [ "GSE293983", "GSE288573", "GSE298665",
                       "GSE254430", "GSE306375", "GSE261489",
                        'GSE310817', 'GSE301140', 'GSE313101',
                        'GSE313071', 'GSE313068', 'GSE313067'
    ]
    ingest_gse_list(retina_gse_list)
