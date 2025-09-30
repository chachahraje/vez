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

# 6. JEMNÉ DOLADĚNÍ ČASOVÁNÍ (TIMING_ADJUSTMENT_MS)
#    Pokud bot kliká konzistentně příliš brzy nebo příliš pozdě,
#    upravte tuto hodnotu.
#    - Kladná hodnota (např. 10) způsobí, že bot počká o 10 ms déle.
#      (Použijte, pokud kliká PŘÍLIŠ BRZY).
#    - Záporná hodnota (např. -5) způsobí, že bot klikne o 5 ms dříve.
#      (Použijte, pokud kliká PŘÍLIŠ POZDĚ).
#    Měňte po malých krocích (5-10 ms).
TIMING_ADJUSTMENT_MS = 5 # Příklad: čeká o 5ms déle

# 7. POČÁTEČNÍ RYCHLOST (INITIAL_SPEED_GUESS_S)
#    Odhadovaná rychlost kostky (v sekundách na sloupec) pro první kolo,
#    než ji bot stihne změřit. Změřte přibližně, jak dlouho trvá,
#    než kostka přejde přes jeden sloupec.
#    Příklad: 0.05s = 50ms na sloupec.
INITIAL_SPEED_GUESS_S = 0.05

# 8. VYSOKÁ PŘESNOST ČEKÁNÍ (BUSY_WAIT_MS)
#    Pro nejpřesnější časování bot použije "busy-wait" smyčku na posledních
#    pár milisekund. Tato hodnota určuje, jak dlouho má tato smyčka běžet.
#    - Zvyšuje zátěž CPU, ale je mnohem přesnější než standardní `time.sleep()`.
#    - Hodnota by měla být o něco vyšší než typická nepřesnost `time.sleep()`
#      na vašem systému (často 10-15 ms).
#    Doporučená hodnota: 15-20 ms.
BUSY_WAIT_MS = 15

# ==============================================================================
# --- KÓD BOTA ---
# Od této části byste neměli nic měnit, pokud nevíte, co děláte.
# ==============================================================================

# Převedení barvy z RGB na BGR (formát, který používá OpenCV)
BLOCK_COLOR_BGR = np.array(BLOCK_COLOR_RGB[::-1])
COLUMN_WIDTH = GAME_REGION['width'] / NUM_COLUMNS

def find_block_position(sct_instance):
    """
    Snímá herní obrazovku, najde kostku a vrátí její přesnou pozici X a index sloupce.
    Vrací (None, None), pokud kostku nenajde.
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
            return None, None

        largest_contour = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(largest_contour)

        if area < 50:
            return None, None

        M = cv2.moments(largest_contour)
        if M["m00"] == 0:
            return None, None

        center_x = int(M["m10"] / M["m00"])
        column_index = int(center_x / COLUMN_WIDTH)

        return center_x, column_index

    except Exception as e:
        print(f"Vyskytla se chyba při zpracování obrazu: {e}")
        return None, None

def main():
    """
    Hlavní smyčka bota s prediktivním časováním.
    """
    print("="*50)
    print("Bot s prediktivním časováním se spustí za 3 sekundy...")
    print("PŘEPNĚTE SE DO OKNA SE HROU!")
    print("Pro ukončení bota stiskněte a držte klávesu 'q'.")
    print("="*50)
    time.sleep(3)

    last_pos_x = None
    last_time = None
    last_column = -1
    direction = 1  # 1 pro doprava, -1 pro doleva
    speed_px_per_s = COLUMN_WIDTH / INITIAL_SPEED_GUESS_S # Počáteční odhad rychlosti
    action_taken = False

    with mss.mss() as sct:
        while not keyboard.is_pressed('q'):

            current_time = time.perf_counter()
            pos_x, current_column = find_block_position(sct)

            if pos_x is None:
                # Pokud kostku nevidíme, resetujeme stav pro další kolo
                if action_taken:
                    print("-" * 20)
                    action_taken = False
                    last_pos_x = None
                    last_column = -1
                continue

            # Měření rychlosti a směru
            if last_pos_x is not None and last_column != current_column:
                delta_time = current_time - last_time
                delta_pos = pos_x - last_pos_x

                if delta_time > 0.001: # Zabráníme dělení nulou
                    # Určení směru
                    new_direction = 1 if delta_pos > 0 else -1
                    if new_direction != direction:
                        print(f"Změna směru! Nový směr: {'doprava' if new_direction == 1 else 'doleva'}")
                        direction = new_direction

                    # Výpočet rychlosti
                    current_speed = abs(delta_pos / delta_time)
                    # Použijeme klouzavý průměr pro stabilizaci rychlosti
                    speed_px_per_s = (speed_px_per_s * 0.8) + (current_speed * 0.2)

            # Aktualizace pozice a času pro další iteraci
            last_pos_x = pos_x
            last_time = current_time
            last_column = current_column

            # --- Prediktivní logika ---
            prediction_trigger_column = TARGET_COLUMN - (PREDICTION_OFFSET * direction)

            if current_column == prediction_trigger_column and not action_taken:

                # Cílová pozice X (střed cílového sloupce)
                target_x = (TARGET_COLUMN + 0.5) * COLUMN_WIDTH

                # Vzdálenost k cíli v pixelech
                distance_to_target_px = abs(target_x - pos_x)

                # Odhadovaný čas k dosažení cíle
                time_to_target_s = distance_to_target_px / speed_px_per_s

                # Přidání manuální korekce a výpočet cílového času
                final_wait_time_s = time_to_target_s + (TIMING_ADJUSTMENT_MS / 1000.0)
                target_press_time = time.perf_counter() + final_wait_time_s

                print(f"Kostka ve sloupci {current_column}. Cíl: {TARGET_COLUMN}. Směr: {'doprava' if direction == 1 else 'doleva'}")
                print(f"Odhadovaný čas do cíle: {time_to_target_s:.3f}s. Celkové čekání: {final_wait_time_s:.4f}s.")

                # Hybridní čekání: time.sleep() + busy-wait
                busy_wait_s = BUSY_WAIT_MS / 1000.0
                sleep_duration = final_wait_time_s - busy_wait_s

                if sleep_duration > 0:
                    time.sleep(sleep_duration)

                # Smyčka pro vysokou přesnost na posledních pár ms
                while time.perf_counter() < target_press_time:
                    pass

                pyautogui.press('space')
                print(f"==> MEZERNÍK! (Cílový sloupec: {TARGET_COLUMN})")

                action_taken = True # Značka, že jsme provedli akci
                time.sleep(COOLDOWN_AFTER_PRESS) # Pauza po stisku

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