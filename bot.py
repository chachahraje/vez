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

# 7. POČÁTEČNÍ DOBA V SLOUPCI (INITIAL_DWELL_TIME_MS)
#    Odhad, jak dlouho (v milisekundách) se kostka zdrží v jednom sloupci,
#    než přeskočí na další. Používá se pro první kolo, než bot změří
#    přesnou hodnotu. Změřte přibližně, jak dlouho trvá jeden "tik" hry.
#    Příklad: 35ms.
INITIAL_DWELL_TIME_MS = 35

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
    Hlavní smyčka bota se synchronizací podle "tiků" hry.
    """
    print("="*50)
    print("Bot se synchronizací podle tiků se spustí za 3 sekundy...")
    print("PŘEPNĚTE SE DO OKNA SE HROU!")
    print("Pro ukončení bota stiskněte a držte klávesu 'q'.")
    print("="*50)
    time.sleep(3)

    last_column = -1
    last_jump_time = 0
    dwell_time_s = INITIAL_DWELL_TIME_MS / 1000.0 # Doba v jednom sloupci
    direction = 1  # 1 pro doprava, -1 pro doleva
    action_taken = False

    with mss.mss() as sct:
        while not keyboard.is_pressed('q'):

            current_column = find_block_column(sct)

            if current_column is None:
                # Pokud kostku nevidíme, resetujeme stav pro další kolo
                if action_taken:
                    print("-" * 20)
                    action_taken = False
                    last_column = -1
                    last_jump_time = 0
                continue

            # Detekce skoku do nového sloupce
            if current_column != last_column:
                current_time = time.perf_counter()

                # Měření času mezi skoky (dwell time)
                if last_jump_time > 0:
                    measured_dwell_time = current_time - last_jump_time
                    # Klouzavý průměr pro stabilizaci měření
                    dwell_time_s = (dwell_time_s * 0.7) + (measured_dwell_time * 0.3)
                    print(f"Nový tik: {dwell_time_s * 1000:.1f} ms")

                # Určení směru
                if last_column != -1:
                    new_direction = 1 if current_column > last_column else -1
                    if new_direction != direction:
                        print(f"Změna směru: {'doprava' if new_direction == 1 else 'doleva'}")
                        direction = new_direction

                last_jump_time = current_time

                # --- Prediktivní logika založená na tiku ---
                prediction_trigger_column = TARGET_COLUMN - (PREDICTION_OFFSET * direction)

                if current_column == prediction_trigger_column and not action_taken:

                    # Předpověď času, kdy kostka skočí do CÍLOVÉHO sloupce
                    predicted_target_jump_time = last_jump_time + dwell_time_s

                    # Cílový čas stisku je mírně po předpovězeném skoku, upravený o jemné doladění
                    total_delay_s = (PRESS_DELAY_MS_AFTER_JUMP + TIMING_ADJUSTMENT_MS) / 1000.0
                    target_press_time = predicted_target_jump_time + total_delay_s

                    print(f"Kostka v trigger sloupci {current_column}. Cíl: {TARGET_COLUMN}")
                    print(f"Čekám na stisk v čase +{((target_press_time - time.perf_counter()) * 1000):.1f} ms")

                    # Hybridní čekání
                    wait_time_s = target_press_time - time.perf_counter()
                    busy_wait_s = BUSY_WAIT_MS / 1000.0
                    sleep_duration = wait_time_s - busy_wait_s

                    if sleep_duration > 0:
                        time.sleep(sleep_duration)

                    # Smyčka pro vysokou přesnost
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