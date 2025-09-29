#!/bin/bash
#SBATCH -A egodat_oit_research_tech_0001
#SBATCH -D /users/mlangstonsmith/tfrrs-scraper/
#SBATCH -J tfrrs_dry_run
#SBATCH -o /users/mlangstonsmith/tfrrs-scraper/debug/output-%j.txt
#SBATCH -e /users/mlangstonsmith/tfrrs-scraper/debug/error-%j.txt
#SBATCH -p htc
#SBATCH -t 1-00:00:00
#SBATCH --mem=200G
#SBATCH -c 1

mkdir -p debug

module purge
module load conda
conda activate tfrrs

python /users/mlangstonsmith/tfrrs-scraper/tfrrsScraperFinal.py