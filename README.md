# TFRRS Scraper

## Create Conda Environment

```
conda env create -f environment.yml
conda activate tfrrs
```

## Install `libgbm1` manually

```
cd ~
wget http://archive.ubuntu.com/ubuntu/pool/main/m/mesa/libgbm1_23.2.1-1ubuntu3.1~22.04.3_amd64.deb
dpkg -x libgbm1_23.2.1-1ubuntu3.1~22.04.3_amd64.deb libgbm1
cp libgbm1/usr/lib/x86_64-linux-gnu/libgbm.so.1* $CONDA_PREFIX/lib/
rm libgbm1_23.2.1-1ubuntu3.1~22.04.3_amd64.deb
rm -r libgbm1
```

Note: In the sbatch script, `export LD_LIBRARY_PATH=$HOME/.conda/envs/tfrrs/lib:$LD_LIBRARY_PATH` is telling it to look in the conda environment for libgbm1 instead of the system installation.

## Install Chromium

```
mkdir -p ~/chromium
cd ~/chromium/
wget https://storage.googleapis.com/chrome-for-testing-public/138.0.7204.168/linux64/chrome-linux64.zip
unzip chrome-linux64.zip
chmod +x ~/chromium/chrome-linux64/chrome
rm chrome-linux64.zip
```

## Install ChromeDriver

```
mkdir -p ~/chromedriver
cd ~/chromedriver/
wget https://storage.googleapis.com/chrome-for-testing-public/138.0.7204.168/linux64/chromedriver-linux64.zip
unzip chromedriver-linux64.zip
mv chromedriver-linux64/chromedriver .
chmod +x chromedriver
rm -r chromedriver-linux64 chromedriver-linux64.zip
```

## Install Playwright

```
playwright install
```