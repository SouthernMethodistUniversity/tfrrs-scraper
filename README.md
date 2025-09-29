# TFRRS Scraper

With permission from FloSports, the parent company of TFRRS, the following 
process was used to scrape data from their site. 

Credit goes to Grady Johnson for writing the initial code.

## Setup

The following code can be run to build a conda environment to run this code:

```
conda env create -f environment.yml
conda activate tfrrs
```

## Step 1: Getting Meet Links

Previous processing was done to collect the meet links into [gendered_meets_01102025.csv](gendered_meets_01102025.csv).

## Step 2: Scraping Results

The `bs4` package was used to scrape data from each meet in batches of about 5,000 meets
using the script called [tfrrsScraperFinal.py](tfrrsScraperFinal.py). Each run was provided
a starting index and ran for 24 hours using the SLURM scheduler on on SMUs supercomputer, 
[M3](https://www.smu.edu/oit/services/m3). The results of all 4 batches can be found at
[this Box link](https://smu.app.box.com/folder/332902814145).