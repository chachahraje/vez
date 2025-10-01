# Tento skript je bot pro hru, kde stavíte věž z kostek.
# Automaticky detekuje pohybující se kostku a stiskne mezerník,
# když je kostka ve správném sloupci.

# --- Potřebné knihovny ---
# Ujistěte se, že máte nainstalované všechny potřebné knihovny.
# Otevřete terminál (příkazový řádek) a spusťte:
# pip install numpy opencv-python pyautogui keyboard mss

import time
import keyboard
import numpy as np
import cv2
import mss
import pyautogui

# ==============================================================================
# --- NASTAVENÍ BOTA ---
# Tuto část musíte upravit podle vaší hry a obrazovky.
# ==============================================================================

# 1. OBLAST HRY (GAME_REGION)
#    Toto je nejdůležitější nastavení. Musíte botovi říct, kde na obrazovce
#    se hra nachází. Je to obdélník definovaný:
#    - 'left': počet pixelů od levého okraje obrazovky
#    - 'top': počet pixelů od horního okraje obrazovky
#    - 'width': šířka herní oblasti v pixelech
#    - 'height': výška herní oblasti v pixelech
#
#    JAK ZJISTIT HODNOTY?
#    Spusťte si Python v terminálu a napište:
#    >>> import pyautogui
#    >>> pyautogui.displayMousePosition()
#    Poté hýbejte myší a terminál vám bude ukazovat její souřadnice (X, Y).
#    - Najeďte myší na LEVÝ HORNÍ roh herní plochy a zapište si X a Y.
#      To jsou vaše hodnoty 'left' a 'top'.
#    - Najeďte myší na PRAVÝ DOLNÍ roh a zapište si X a Y.
#    - 'width' = (pravý dolní X) - (levý horní X)
#    - 'height' = (pravý dolní Y) - (levý horní Y)
#
# Příklad:
GAME_REGION = {'left': 660, 'top': 518, 'width': 603, 'height': 64}


# 2. BARVA KOSTKY (BLOCK_COLOR_RGB)
#    Zadejte barvu kostky, kterou má bot hledat.
#    Hodnoty jsou v RGB formátu (červená, zelená, modrá).
#    Tvůj příklad byl RGB (236, 168, 44).
BLOCK_COLOR_RGB = (236, 168, 44)

#    Jak moc se může skutečná barva lišit od zadané.
#    Větší číslo znamená větší toleranci (např. pro různé odstíny).
COLOR_TOLERANCE = 25


# 3. HERNÍ PARAMETRY
#    Počet sloupců, mezi kterými kostka přeskakuje.
NUM_COLUMNS = 10

#    CÍLOVÝ SLOUPEC (TARGET_COLUMN)
#    Do kterého sloupce má bot mířit? Čísluje se od 0.
#    Pokud máte 10 sloupců (0 až 9), sloupec 4 je pátý zleva.
#    Toto je nejdůležitější hodnota pro míření.
TARGET_COLUMN = 8


# 4. RYCHLOST A ČEKÁNÍ
#    Krátká pauza po stisknutí mezerníku, aby se nestiskl vícekrát
#    pro jednu kostku. Hodnota je ve vteřinách.
COOLDOWN_AFTER_PRESS = 0.1 # 100ms

# ==============================================================================
# --- KÓD BOTA ---
# Od této části byste neměli nic měnit, pokud nevíte, co děláte.
# ==============================================================================

# Převedení barvy z RGB na BGR (formát, který používá OpenCV)
BLOCK_COLOR_BGR = np.array(BLOCK_COLOR_RGB[::-1])
COLUMN_WIDTH = GAME_REGION['width'] / NUM_COLUMNS

def find_block_column(sct_instance):
    """
    Snímá herní obrazovku, najde kostku a vrátí index sloupce (0-9).
    Pokud kostku nenajde, vrátí None.
    """
    try:
        # 1. Snímání obrazovky pomocí mss (je to velmi rychlé)
        img = sct_instance.grab(GAME_REGION)
        img_np = np.array(img)
        # Převedení z BGRA (formát mss) na BGR (formát OpenCV)
        frame = cv2.cvtColor(img_np, cv2.COLOR_BGRA2BGR)

        # 2. Vytvoření masky pro hledanou barvu
        lower_bound = np.maximum(0, BLOCK_COLOR_BGR - COLOR_TOLERANCE)
        upper_bound = np.minimum(255, BLOCK_COLOR_BGR + COLOR_TOLERANCE)
        mask = cv2.inRange(frame, lower_bound, upper_bound)

        # 3. Nalezení největšího objektu (kontury) v masce
        contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None  # Kostka nenalezena

        largest_contour = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(largest_contour)

        # Ignorování malých teček, které mohou být šum
        if area < 50:  # Tuto hodnotu můžete upravit podle velikosti kostky
            return None

        # 4. Výpočet pozice středu kostky
        M = cv2.moments(largest_contour)
        if M["m00"] == 0:
            return None

        center_x = int(M["m10"] / M["m00"])

        # 5. Určení sloupce podle pozice
        column_index = int(center_x / COLUMN_WIDTH)

        return column_index

    except Exception as e:
        print(f"Vyskytla se chyba při zpracování obrazu: {e}")
        return None


def main():
    """
    Hlavní smyčka bota s novou synchronizační logikou.
    """
    print("="*50)
    print("Bot se spustí za 3 sekundy...")
    print("PŘEPNĚTE SE DO OKNA SE HROU!")
    print("Pro ukončení bota stiskněte a držte klávesu 'q'.")
    print("="*50)
    time.sleep(3)

    last_seen_column = -1

    # Stavové proměnné pro synchronizaci
    first_sighting_time = None
    is_initialized = False
    has_seen_column_zero = False

    # Vytvoření instance mss pro snímání obrazovky
    with mss.mss() as sct:
        while True:
            if keyboard.is_pressed('q'):
                print("\nKlávesa 'q' stisknuta, bot se ukončuje.")
                break

            current_column = find_block_column(sct)

            if current_column is None:
                # Pokud kostku nevidíme, nic neděláme
                continue

            # --- Logika pro počáteční 2s synchronizaci ---
            if first_sighting_time is None:
                print("Kostka poprvé detekována. Spouštím 2s inicializační časovač...")
                first_sighting_time = time.time()

            if not is_initialized:
                if (time.time() - first_sighting_time) > 2.0:
                    print("Inicializace dokončena. Čekám na začátek cyklu (sloupec 0).")
                    is_initialized = True
                else:
                    # Během prvních 2 sekund jen pozorujeme a aktualizujeme last_seen_column
                    last_seen_column = current_column
                    continue

            # --- Logika pro čekání na celý cyklus (detekce sloupce 0) ---
            if not has_seen_column_zero and current_column == 0:
                print("Detekován začátek cyklu (sloupec 0). Bot je nyní plně aktivní.")
                has_seen_column_zero = True

            # --- Podmínka pro stisk ---
            # Stiskneme pouze pokud:
            # 1. Je dokončena 2s inicializace
            # 2. Viděli jsme začátek cyklu (sloupec 0)
            # 3. Kostka je v cílovém sloupci
            # 4. Je to poprvé, co ji v tomto sloupci vidíme (prevence dvojkliku)
            if is_initialized and has_seen_column_zero and current_column == TARGET_COLUMN and current_column != last_seen_column:
                 pyautogui.press('space')
                 print(f"Kostka v cílovém sloupci {TARGET_COLUMN}! Stisknut mezerník!")

                 # Počkáme chvíli, abychom nereagovali na stejnou kostku znovu
                 time.sleep(COOLDOWN_AFTER_PRESS)

                 # Resetujeme podmínku pro další cyklus
                 print("Čekám na další cyklus (sloupec 0)...")
                 has_seen_column_zero = False

            # Zapamatujeme si, kde byla kostka naposledy
            last_seen_column = current_column

if __name__ == "__main__":
    print("Vítejte v botovi pro skládání věže!")
    print("Před spuštěním prosím nastavte hodnoty v sekci 'NASTAVENÍ BOTA'.")
    print("\nPotřebné knihovny: pip install numpy opencv-python pyautogui keyboard mss")

    # Zeptáme se uživatele, zda chce spustit bota
    run_bot = input("Chcete spustit bota nyní? (ano/ne): ")
    if run_bot.lower() in ['a', 'ano', 'y', 'yes']:
        main()
    else:
        print("Bot nebyl spuštěn. Upravte nastavení a zkuste to znovu.")