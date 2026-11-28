@echo off
rem Liga os dois robos da conta demo, cada um em uma janela. O MetaTrader 5 precisa estar instalado e com a conta demo salva.
cd /d %~dp0
start "Frente 1 - tendencia ouro e prata" cmd /k py -3.12 -m prop.live.mt5_trend --live --loop
start "Frente 3 - abertura de NY" cmd /k py -3.12 -m prop.live.ny_open_demo --live --loop
