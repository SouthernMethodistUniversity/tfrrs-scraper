# TFRRS Scraper

## Create Conda Environment

```
conda env create -f environment.yml
conda activate tfrrs
```

## Run SBATCH script

This should take approximately 24 hours for every 5,375 links.

```
cd ~/tfrrs-scraper
sbatch dry_run.sbatch
```