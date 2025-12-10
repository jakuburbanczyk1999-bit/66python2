# INSTRUKCJA WGRYWANIA BOTÓW NN NA SERWER
# Miedziowe Karty - Neural Network Bots Deployment

## KROK 1: Przygotowanie plików lokalnie

Upewnij się, że masz te pliki gotowe:
- nn_training/               (cały folder)
- nn_training/checkpoints/best_model.pt  (wytrenowany model ~2MB)
- boty.py                    (zaktualizowany z NN botami)
- create_bots.py             (zaktualizowany z nowymi kontami)

## KROK 2: Połączenie z serwerem

```bash
ssh user@twoj-serwer.pl
# lub przez PuTTY na Windows
```

## KROK 3: Skopiowanie plików na serwer

### Opcja A: Przez SCP (Linux/Mac/Git Bash)
```bash
# Z lokalnego komputera:
cd C:\Users\jakub\Desktop\miedziowe-karty

# Kopiuj cały folder nn_training
scp -r nn_training/ user@serwer:/sciezka/do/miedziowe-karty/

# Kopiuj zaktualizowane pliki
scp boty.py user@serwer:/sciezka/do/miedziowe-karty/
scp create_bots.py user@serwer:/sciezka/do/miedziowe-karty/
```

### Opcja B: Przez SFTP/FileZilla
1. Połącz się z serwerem
2. Skopiuj folder `nn_training` do katalogu projektu
3. Nadpisz `boty.py` i `create_bots.py`

### Opcja C: Przez Git (jeśli używasz)
```bash
# Lokalnie:
git add nn_training/ boty.py create_bots.py
git commit -m "Add Neural Network bots"
git push

# Na serwerze:
cd /sciezka/do/miedziowe-karty
git pull
```

## KROK 4: Instalacja zależności na serwerze

```bash
cd /sciezka/do/miedziowe-karty

# Aktywuj venv
source venv/bin/activate  # Linux
# lub: .\venv\Scripts\activate  # Windows

# Zainstaluj PyTorch (jeśli nie ma)
pip install torch --index-url https://download.pytorch.org/whl/cpu
# LUB dla GPU:
# pip install torch --index-url https://download.pytorch.org/whl/cu118
```

## KROK 5: Weryfikacja plików

```bash
# Sprawdź czy model istnieje
ls -la nn_training/checkpoints/
# Powinno pokazać: best_model.pt (~2MB)

# Test importu
python -c "from nn_training.nn_bot import NeuralNetworkBot; print('OK')"
```

## KROK 6: Tworzenie kont botów w bazie

```bash
# Pokaż istniejące boty
python create_bots.py --list

# Stwórz nowe konta (tylko brakujące)
python create_bots.py --create

# Lub pełna procedura (list + create + list)
python create_bots.py
```

Oczekiwany output:
```
✅ NeuralMaster - utworzono (ID: 21, algorytm: nn_topplayer)
✅ DeepPlayer66 - utworzono (ID: 22, algorytm: nn_topplayer)
...
📊 Podsumowanie: utworzono 10, pominięto 20
```

## KROK 7: Restart serwera

### Jeśli używasz systemd:
```bash
sudo systemctl restart miedziowe-karty
# lub nazwa twojego serwisu
```

### Jeśli używasz PM2:
```bash
pm2 restart miedziowe-karty
```

### Jeśli ręcznie:
```bash
# Znajdź proces
ps aux | grep uvicorn

# Zabij stary
kill -9 <PID>

# Uruchom nowy
cd /sciezka/do/miedziowe-karty
source venv/bin/activate
nohup uvicorn main:app --host 0.0.0.0 --port 8000 &
```

## KROK 8: Weryfikacja

```bash
# Sprawdź logi
tail -f /var/log/miedziowe-karty.log
# lub: pm2 logs

# Test API (jeśli masz endpoint)
curl http://localhost:8000/api/bots
```

## KROK 9: Test w przeglądarce

1. Otwórz portal: https://twoja-domena.pl
2. Wejdź do lobby
3. Sprawdź czy nowe boty (NeuralMaster, DeepPlayer66, etc.) są widoczne
4. Zagraj testową grę z botem NN

---

## ROZWIĄZYWANIE PROBLEMÓW

### Problem: "ModuleNotFoundError: No module named 'nn_training'"
```bash
# Upewnij się że folder nn_training jest w głównym katalogu projektu
ls -la nn_training/
# Powinien zawierać: __init__.py, nn_bot.py, network.py, config.py, etc.
```

### Problem: "No module named 'torch'"
```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

### Problem: "Model not found"
```bash
# Sprawdź ścieżkę modelu
ls nn_training/checkpoints/best_model.pt

# Jeśli brak, skopiuj z lokalnego komputera
scp nn_training/checkpoints/best_model.pt user@serwer:/sciezka/nn_training/checkpoints/
```

### Problem: Boty NN grają losowo
```bash
# Sprawdź czy model się ładuje
python -c "
from nn_training.nn_bot import NeuralNetworkBot
bot = NeuralNetworkBot()
print(f'Model loaded, device: {bot.device}')
"
```

---

## PLIKI DO SKOPIOWANIA - CHECKLIST

[ ] nn_training/__init__.py
[ ] nn_training/config.py
[ ] nn_training/network.py
[ ] nn_training/nn_bot.py
[ ] nn_training/state_encoder.py
[ ] nn_training/checkpoints/best_model.pt  (WAŻNE - wytrenowany model!)
[ ] boty.py (zaktualizowany)
[ ] create_bots.py (zaktualizowany)

---

## SZYBKA WERSJA (jedna komenda)

```bash
# Na lokalnym komputerze (PowerShell):
cd C:\Users\jakub\Desktop\miedziowe-karty
scp -r nn_training boty.py create_bots.py user@serwer:/app/miedziowe-karty/

# Na serwerze:
ssh user@serwer
cd /app/miedziowe-karty
source venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cpu
python create_bots.py
sudo systemctl restart miedziowe-karty
```
