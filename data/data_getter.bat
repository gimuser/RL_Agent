@echo off
REM Download Kaggle dataset train/test files using Python and kagglehub.
REM Usage:
REM   python download_kaggle_dataset.py
REM   python download_kaggle_dataset.py --dataset avijitjana101/microsoft-soc-dataset
REM   python download_kaggle_dataset.py --output-dir ..\data

SET PYTHON=python
%PYTHON% download_kaggle_dataset.py %*
