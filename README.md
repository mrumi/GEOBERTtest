# GEOTest
# Installation

`git clone https://github.com/mrumi/GEOTest.git`

`conda env create -f environment.yml`

`conda activate GEOTest`

`cd GEOTest`

create .env file using following command

`touch .env`

`nano .env`

copy-paste following information and replace url and api key using your credentials

`QDRANT_URL=https://your-cluster.cloud.qdrant.io` 

`QDRANT_API_KEY=your_qdrant_api_key`

save the file. 

# Data Preprocessing

`cd codes`

`python preprocess.py`

