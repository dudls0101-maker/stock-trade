@echo off
cd /d C:\Users\indong\CascadeProjects\auto_trader
py -3.12 monthly_recheck.py >> logs\monthly_recheck.log 2>&1
echo Done. Check reports\monthly_recheck_*.md
pause
