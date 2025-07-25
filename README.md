# TFRRS Scraper

## Create Conda Environment

```
conda env create -f environment.yml
conda activate tfrrs
```

## Run SBATCH script

This should take approximately 12 hours, which gives 2 seconds between requests.

```
cd ~/tfrrs-scraper
sbatch dry_run.sbatch
```