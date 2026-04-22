#!/bin/sh

git clone https://github.com/mrumi/GEOTest.git
conda env create -f environment.yml
conda activate GEOTest
cd GEOTest

