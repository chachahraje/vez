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
COOLDOWN_AFTER_PRESS = 0.2 # 200ms, delší pauza pro prediktivní logiku

# ==============================================================================
# --- POKROČILÉ NASTAVENÍ PRO PŘESNÉ ČASOVÁNÍ ---
# ==============================================================================

# 5. PŘEDVÍDÁNÍ (PREDICTION)
#    Kolik sloupců "dopředu" má bot reagovat.
#    Pokud je cíl sloupec 8 a PREDICTION_OFFSET = 1, bot stiskne mezerník,
#    když je kostka ve sloupci 7 (při pohybu zleva doprava).
#    To kompenzuje zpoždění mezi detekcí a stiskem.
#    Doporučená hodnota: 1 nebo 2.
PREDICTION_OFFSET = 1

# 6. LATENCE DETEKCE (DETECTION_LATENCY_MS)
#    Toto je nejdůležitější nastavení pro synchronizaci.
#    Určuje, kolik milisekund uplyne mezi okamžikem, kdy hra *zobrazí*
#    kostku v novém sloupci, a okamžikem, kdy ji náš bot *detekuje*.
#    Tato latence je způsobena snímáním obrazovky a zpracováním obrazu.
#    - Laďte tuto hodnotu, dokud změřený "Nový tik" nebude stabilně
#      odpovídat skutečné frekvenci hry (např. 33-35 ms).
#    Doporučená startovní hodnota: 10-15 ms.
DETECTION_LATENCY_MS = 15

# 7. HERNÍ TIK (GAME_TICK_MS)
#    Základní "tep" hry v milisekundách. Toto je konstantní hodnota,
#    která řídí veškeré časování. Podle vašich informací je to 33ms.
#    Tuto hodnotu byste neměli měnit, pokud si nejste jisti, že se
#    základní frekvence hry změnila.
GAME_TICK_MS = 33

# 8. ZPOŽDĚNÍ STISKU PO SKOKU (PRESS_DELAY_MS_AFTER_JUMP)
#    Toto je klíčové nastavení pro přesné zacílení.
#    Určuje, kolik milisekund má bot počkat po začátku dalšího "tiku"
#    (když kostka skočí do cílového sloupce), než stiskne mezerník.
#    Chcete trefit okno 5-10ms, takže hodnota by měla být v tomto rozmezí.
#    - Začněte s hodnotou okolo 5 a jemně ji laďte.
PRESS_DELAY_MS_AFTER_JUMP = 5

# 9. VYSOKÁ PŘESNOST ČEKÁNÍ (BUSY_WAIT_MS)
#    Pro nejpřesnější časování bot použije "busy-wait" smyčku.
#    Tato hodnota by měla být o něco vyšší než `PRESS_DELAY_MS_AFTER_JUMP`.
#    Doporučená hodnota: 15-20 ms.
BUSY_WAIT_MS = 15

# ==============================================================================
# --- KÓD BOTA ---
# Od této části byste neměli nic měnit, pokud nevíte, co děláte.
# ==============================================================================

# Převedení barvy z RGB na BGR (formát, který používá OpenCV)
BLOCK_COLOR_BGR = np.array(BLOCK_COLOR_RGB[::-1])
COLUMN_WIDTH = GAME_REGION['width'] / NUM_COLUMNS

def find_block_column(sct_instance):
    """
    Snímá herní obrazovku, najde kostku a vrátí index jejího sloupce (0-9).
    Pokud kostku nenajde, vrátí None.
    """
    try:
        img = sct_instance.grab(GAME_REGION)
        img_np = np.array(img)
        frame = cv2.cvtColor(img_np, cv2.COLOR_BGRA2BGR)

        lower_bound = np.maximum(0, BLOCK_COLOR_BGR - COLOR_TOLERANCE)
        upper_bound = np.minimum(255, BLOCK_COLOR_BGR + COLOR_TOLERANCE)
        mask = cv2.inRange(frame, lower_bound, upper_bound)

        contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None

        largest_contour = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(largest_contour)

        if area < 50:
            return None

        M = cv2.moments(largest_contour)
        if M["m00"] == 0:
            return None

        center_x = int(M["m10"] / M["m00"])
        column_index = int(center_x / COLUMN_WIDTH)

        return column_index

    except Exception as e:
        print(f"Vyskytla se chyba při zpracování obrazu: {e}")
        return None

def main():
    """
    Hlavní smyčka bota s prediktivním časováním a bezpečnostní synchronizací.
    """
    print("="*50)
    print("Finální verze bota se spustí za 3 sekundy...")
    print("PŘEPNĚTE SE DO OKNA SE HROU!")
    print("Pro ukončení bota stiskněte a držte klávesu 'q'.")
    print("="*50)
    time.sleep(3)

    last_column = -1
    direction = 1
    action_taken = False

    # Stavové proměnné pro bezpečnostní synchronizaci
    first_detection_time = None
    is_initialized = False
    has_seen_full_cycle = False

    with mss.mss() as sct:
        while not keyboard.is_pressed('q'):

            current_column = find_block_column(sct)

            if current_column is None:
                if action_taken:
                    print("-" * 20)
                    action_taken = False
                    last_column = -1
                    # Po úspěšné akci čekáme na nový celý cyklus
                    has_seen_full_cycle = False
                continue

            # --- Bezpečnostní synchronizace ---
            if first_detection_time is None:
                print("Kostka poprvé detekována. Spouštím 2s inicializační časovač...")
                first_detection_time = time.perf_counter()

            if not is_initialized:
                if (time.perf_counter() - first_detection_time) > 2.0:
                    print("Inicializace dokončena. Bot je připraven k akci.")
                    is_initialized = True
                else:
                    # Během prvních 2 sekund jen pozorujeme
                    last_column = current_column
                    continue

            # Detekce skoku do nového sloupce
            if current_column != last_column:

                # --- Logika pro čekání na celý cyklus (sloupec 0) ---
                if not has_seen_full_cycle and current_column == 0:
                    print("Detekován začátek cyklu (sloupec 0). Bot je nyní plně aktivní.")
                    has_seen_full_cycle = True

                # --- Prediktivní logika (spustí se až po synchronizaci) ---
                detection_time = time.perf_counter()
                latency_s = DETECTION_LATENCY_MS / 1000.0
                inferred_jump_start_time = detection_time - latency_s
                game_tick_s = GAME_TICK_MS / 1000.0
                print(f"Detekován skok. Synchronizuji s konstantním tikem: {GAME_TICK_MS} ms")

                if last_column != -1:
                    new_direction = 1 if current_column > last_column else -1
                    if new_direction != direction:
                        print(f"Změna směru: {'doprava' if new_direction == 1 else 'doleva'}")
                        direction = new_direction

                prediction_trigger_column = TARGET_COLUMN - (PREDICTION_OFFSET * direction)

                # FINÁLNÍ PODMÍNKA PRO STISK:
                if is_initialized and has_seen_full_cycle and current_column == prediction_trigger_column and not action_taken:

                    predicted_target_jump_time = inferred_jump_start_time + game_tick_s
                    press_delay_s = PRESS_DELAY_MS_AFTER_JUMP / 1000.0
                    target_press_time = predicted_target_jump_time + press_delay_s

                    print(f"Kostka v trigger sloupci {current_column}. Cíl: {TARGET_COLUMN}")
                    print(f"Čekám na stisk v čase +{((target_press_time - time.perf_counter()) * 1000):.1f} ms")

                    wait_time_s = target_press_time - time.perf_counter()
                    if wait_time_s > 0:
                        busy_wait_s = BUSY_WAIT_MS / 1000.0
                        sleep_duration = wait_time_s - busy_wait_s
                        if sleep_duration > 0:
                            time.sleep(sleep_duration)
                        while time.perf_counter() < target_press_time:
                            pass

                    pyautogui.press('space')
                    print(f"==> MEZERNÍK! (Cílový sloupec: {TARGET_COLUMN})")

                    action_taken = True
                    time.sleep(COOLDOWN_AFTER_PRESS)

                last_column = current_column

        print("\nKlávesa 'q' stisknuta, bot se ukončuje.")

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